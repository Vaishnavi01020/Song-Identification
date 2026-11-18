#!/usr/bin/env python3
"""
CD song namer (command line)
----------------------------
Takes ripped CD tracks (WAV/FLAC), identifies each song ONE AT A TIME, and saves it as
    "Song Title - Artist.wav"

Per track:
    1. ACRCloud (REST API) -> candidate songs
    2. Qwen2 (free, local via Ollama) -> picks the best candidate, cleans title + artist
    3. Save with the new name and write a log row

Qwen2 only chooses among ACRCloud's candidates. If its answer doesn't match a real
candidate, or Ollama isn't running, simple rule-based cleanup is used instead.
Nothing identified -> "Track07 - Unknown Artist.wav".

Environment variables:
    ACR_HOST, ACR_ACCESS_KEY, ACR_ACCESS_SECRET
    OLLAMA_URL    optional, default http://localhost:11434
    OLLAMA_MODEL  optional, default qwen2:7b
"""
import argparse
import csv
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from acr_client import ACRError, identify_track

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2:7b")
AUDIO_EXTS = {".wav", ".flac"}

QWEN_SYSTEM = """You clean song metadata for a music library.
You receive a JSON list of candidate songs from a fingerprint service, best first.
Pick the single best candidate and return ONLY this JSON:
{"title": "...", "artist": "..."}
Rules:
- Use ONLY information found in the candidates. Never use outside knowledge or invent anything.
- Title: remove version tags like (Remastered), (Live), [Explicit], "From <film>" and similar clutter.
- Artist: the main singer(s) only, joined with ", ". Keep one consistent spelling.
- Prefer the candidate with more votes, then the higher score.
- If no candidate is usable, return {"title": "", "artist": ""}."""


# ----------------------------------------------------------------------------
# Cleanup: Qwen2 first, rules as fallback
# ----------------------------------------------------------------------------
def clean_title_rules(title):
    t = re.sub(r"\s*[\(\[].*?[\)\]]", "", title)  # (Remastered), [Live] ...
    t = re.sub(r"\s*-\s*(remaster(ed)?|live|from)\b.*$", "", t, flags=re.I)
    return t.strip()


def rule_based(candidate):
    return {
        "title": clean_title_rules(candidate["title"]),
        "artist": ", ".join(candidate["artists"][:2]),
    }


def ask_qwen(candidates):
    """Ask local Qwen2 to choose + clean. Returns {"title","artist"} or None."""
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": QWEN_SYSTEM},
            {"role": "user", "content": json.dumps(candidates, ensure_ascii=False)},
        ],
    }
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=180)
        r.raise_for_status()
        out = json.loads(r.json()["message"]["content"])
        title, artist = str(out.get("title", "")).strip(), str(out.get("artist", "")).strip()
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"    (Qwen2 unavailable: {e}; using rule-based cleanup)")
        return None
    return {"title": title, "artist": artist} if title and artist else None


def grounded(answer, candidates):
    """Anti-hallucination guard: Qwen's title must closely match a real candidate title."""
    a = answer["title"].lower()
    return any(
        difflib.SequenceMatcher(None, a, clean_title_rules(c["title"]).lower()).ratio() >= 0.6
        for c in candidates
    )


def decide(candidates, use_llm=True):
    """Return (title, artist), or (None, None) if there is nothing usable."""
    if not candidates:
        return None, None
    answer = ask_qwen(candidates) if use_llm else None
    if answer and grounded(answer, candidates):
        return answer["title"], answer["artist"]
    if answer:
        print("    (Qwen2 answer didn't match any candidate; using rule-based cleanup)")
    fb = rule_based(candidates[0])
    if fb["title"] and fb["artist"]:
        return fb["title"], fb["artist"]
    return None, None


# ----------------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------------
def safe_name(text, limit=100):
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:limit].rstrip(" .")


def unique_path(folder, base, ext):
    p = folder / f"{base}{ext}"
    n = 2
    while p.exists():  # never overwrite
        p = folder / f"{base} ({n}){ext}"
        n += 1
    return p


def rip_cd(out_dir):
    """Linux/macOS: rip with cdparanoia. On Windows rip with Exact Audio Copy / dBpoweramp / fre:ac."""
    if not shutil.which("cdparanoia"):
        sys.exit("cdparanoia not found. Install it, or rip the CD with another tool and omit --rip.")
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Ripping CD (this takes a few minutes)...")
    subprocess.run(["cdparanoia", "-B"], cwd=out_dir, check=True)


def main():
    ap = argparse.ArgumentParser(description="Identify ripped CD tracks and save them as 'Title - Artist.wav'")
    ap.add_argument("--input", default="ripped", help="folder with ripped tracks (default: ripped)")
    ap.add_argument("--output", default="Music", help="folder for named songs (default: Music)")
    ap.add_argument("--rip", action="store_true", help="rip the CD into --input first (needs cdparanoia)")
    ap.add_argument("--no-llm", action="store_true", help="skip Qwen2, use rule-based cleanup only")
    args = ap.parse_args()

    in_dir, out_dir = Path(args.input), Path(args.output)
    if args.rip:
        rip_cd(in_dir)
    tracks = sorted(p for p in in_dir.glob("*") if p.suffix.lower() in AUDIO_EXTS)
    if not tracks:
        sys.exit(f"No .wav/.flac files found in '{in_dir}'.")
    out_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "log.csv"
    new_log = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as lf:
        log = csv.writer(lf)
        if new_log:
            log.writerow(["track", "source_file", "title", "artist", "saved_as", "status"])

        for n, src in enumerate(tracks, start=1):  # one song at a time, like the flowchart
            print(f"[{n}/{len(tracks)}] {src.name}")
            error = None
            try:
                candidates = identify_track(src)
                title, artist = decide(candidates, use_llm=not args.no_llm)
            except ACRError as e:
                if "Missing environment" in str(e) or "ffmpeg" in str(e):
                    sys.exit(str(e))  # setup problem: stop instead of marking every track unknown
                error, title, artist = str(e), None, None
            except Exception as e:  # keep going on one bad track
                error, title, artist = str(e), None, None

            if title and artist:
                base, status = safe_name(f"{title} - {artist}"), "identified"
                print(f"    Title : {title}\n    Artist: {artist}")
            else:
                title, artist = "", ""
                base = f"Track{n:02d} - Unknown Artist"
                status = "error" if error else "unknown"
                print(f"    {'Error: ' + error if error else 'Not identified'} -> saving as Unknown Artist")

            dest = unique_path(out_dir, base, src.suffix.lower())
            shutil.copy2(src, dest)  # your ripped original stays untouched
            log.writerow([n, src.name, title, artist, dest.name, status])
            lf.flush()
            print(f"    Saved : {dest.name}")

    print(f"\nDone. Songs are in '{out_dir}', log in '{log_path}'.")


if __name__ == "__main__":
    main()