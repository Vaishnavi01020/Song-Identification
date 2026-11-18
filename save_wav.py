"""Step 3 - Save every track in the folder as TrackNN.wav (skips tracks already there)."""
import time
import wave
from pathlib import Path

from read_audio import CHANNELS, SAMPLE_RATE, read_track_pcm


def track_path(folder: Path, number: int) -> Path:
    return Path(folder) / f"Track{number:02d}.wav"


def save_wav(path: Path, pcm: bytes):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


def rip_all(device, tracks, folder: Path, on_ready=None, timeout=180):
    """Rip track by track. Each finished track is passed to on_ready(number, path) at once,
    so identification can run while the next track is still being read.
    Tracks already in the folder are skipped. Returns [(number, path), ...]."""
    ripped = []

    def ready(n):
        ripped.append((n, track_path(folder, n)))
        if on_ready:
            on_ready(n, track_path(folder, n))

    for t in tracks:
        n = t["number"]
        if track_path(folder, n).exists():
            print(f"[rip {n}/{len(tracks)}] already there, skipping")
            ready(n)
            continue
        print(f"[rip {n}/{len(tracks)}] reading track {n} ...")
        start = time.time()
        try:
            save_wav(track_path(folder, n), read_track_pcm(device, t, timeout))
        except Exception as e:  # one bad track must not stop the whole CD
            track_path(folder, n).unlink(missing_ok=True)  # never keep a half-written file
            print(f"    SKIPPED: {e}")
            continue
        print(f"    saved Track{n:02d}.wav in {time.time() - start:.0f}s")
        ready(n)
    return sorted(ripped)