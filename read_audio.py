"""Step 2 - Read audio from CD (one track as raw PCM, with a time limit)."""
import argparse
import subprocess

from read_tracks import read_track_list

SAMPLE_RATE = 44100
CHANNELS = 2  # 16-bit stereo = standard audio CD format


def read_track_pcm(device, track, timeout=None) -> bytes:
    cmd = [
        "ffmpeg", "-v", "error", "-f", "libcdio",
        "-ss", f"{track['start']:.3f}", "-i", device,
        "-t", f"{track['duration']:.3f}",
        "-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "pipe:1",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Track {track['number']} took longer than {timeout:.0f}s")
    if r.returncode != 0:
        raise RuntimeError(f"Track {track['number']} read failed:\n{r.stderr.decode(errors='replace').strip()}")
    if not r.stdout:
        raise RuntimeError(f"Track {track['number']}: no audio data was read.")
    return r.stdout




if __name__ == "__main__":  # quick test: python read_audio.py --track 1
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", default=None)
    ap.add_argument("--track", type=int, default=1)
    args = ap.parse_args()
    device, tracks = read_track_list(args.drive)
    track = next((t for t in tracks if t["number"] == args.track), None)
    if track is None:
        raise SystemExit(f"Track {args.track} not found (disc has {len(tracks)} tracks).")
    pcm = read_track_pcm(device, track)
    print(f"Read {len(pcm) / 1_048_576:.1f} MB of PCM data from track {args.track}")