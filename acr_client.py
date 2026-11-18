"""ACRCloud client (plain HTTPS REST API, no SDK needed).

Needs ffmpeg + ffprobe on PATH (to cut small 8 kHz mono clips for upload).
Environment variables: ACR_HOST, ACR_ACCESS_KEY, ACR_ACCESS_SECRET
"""
import base64
import hashlib
import hmac
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests

HTTP_URI = "/v1/identify"
NO_RESULT = 1001       # no match found
NO_FINGERPRINT = 2004  # silent / too-quiet audio
FATAL_CODES = {
    3001: "Check ACR_ACCESS_KEY (run: python check_acr.py)",
    3014: "Check ACR_ACCESS_KEY and ACR_ACCESS_SECRET belong to the same project (run: python check_acr.py)",
    3003: "Your ACRCloud request limit is used up; try again later or check your plan",
}


class ACRError(RuntimeError):
    """Network or ACRCloud API error. Not the same as 'song not found'."""


class ACRSetupError(ACRError):
    """Missing keys or ffmpeg: every track would fail, so the program stops."""


def _config():
    missing = [k for k in ("ACR_HOST", "ACR_ACCESS_KEY", "ACR_ACCESS_SECRET") if not os.environ.get(k)]
    if missing:
        raise ACRSetupError(f"Missing environment variables: {', '.join(missing)}")
    host = os.environ["ACR_HOST"].strip().replace("https://", "").replace("http://", "").strip("/")
    return host, os.environ["ACR_ACCESS_KEY"].strip(), os.environ["ACR_ACCESS_SECRET"].strip()


def make_signature(access_key, access_secret, data_type, signature_version, timestamp):
    string_to_sign = "\n".join(["POST", HTTP_URI, access_key, data_type, signature_version, timestamp])
    digest = hmac.new(access_secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def recognize_bytes(wav_bytes, timeout=20):
    """Send one audio clip to ACRCloud; return the JSON response."""
    host, access_key, access_secret = _config()
    timestamp = str(int(time.time()))
    data = {
        "access_key": access_key,
        "sample_bytes": len(wav_bytes),
        "timestamp": timestamp,
        "signature": make_signature(access_key, access_secret, "audio", "1", timestamp),
        "data_type": "audio",
        "signature_version": "1",
    }
    files = {"sample": ("sample.wav", wav_bytes, "audio/wav")}
    try:
        r = requests.post(f"https://{host}{HTTP_URI}", data=data, files=files, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        raise ACRError(f"Could not reach ACRCloud: {e}") from e


def parse_result(resp):
    """One candidate dict, or None if no match. Raises on API errors."""
    status = resp.get("status", {})
    code = status.get("code")
    if code in (NO_RESULT, NO_FINGERPRINT):
        return None
    if code in FATAL_CODES:
        raise ACRSetupError(f"ACRCloud error {code}: {status.get('msg')}. {FATAL_CODES[code]}")
    if code != 0:
        raise ACRError(f"ACRCloud error {code}: {status.get('msg')}")
    music = resp.get("metadata", {}).get("music", [])
    if not music:
        return None
    m = music[0]
    return {
        "title": m.get("title") or "",
        "artists": [a.get("name") for a in m.get("artists", []) if a.get("name")],
        "album": (m.get("album") or {}).get("name") or "",
        "score": m.get("score"),
        "acrid": m.get("acrid"),
    }


def _need_ffmpeg():
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise ACRSetupError("ffmpeg/ffprobe not found. Install ffmpeg and make sure it is on your PATH.")


def duration_seconds(path):
    _need_ffmpeg()
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def cut_sample(path, start, length):
    """`length` seconds from `start`, as small 8 kHz mono WAV bytes."""
    _need_ffmpeg()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "sample.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(length),
             "-i", str(path), "-ac", "1", "-ar", "8000", str(out)],
            check=True,
        )
        return out.read_bytes()


def identify_track(path, rec_length=15, slice_points=(0.25, 0.5, 0.75)):
    """Try up to 3 slices of the track; return candidates sorted by votes (best first)."""
    total = duration_seconds(path)
    hits = []
    for p in slice_points:
        start = 0.0 if total <= rec_length else max(0.0, total * p - rec_length / 2)
        hit = parse_result(recognize_bytes(cut_sample(path, start, rec_length)))
        if hit:
            hits.append(hit)
        if len(hits) >= 2 and hits[0]["acrid"] == hits[1]["acrid"]:
            break  # two slices agree: save an API call
    votes = {}
    for h in hits:
        votes.setdefault(h["acrid"], dict(h, votes=0))["votes"] += 1
    return sorted(votes.values(), key=lambda c: c["votes"], reverse=True)