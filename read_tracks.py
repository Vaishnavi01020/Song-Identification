"""Step 1 - Insert audio CD: find the drive and read the list of tracks."""
import json
import string
import subprocess
from pathlib import Path

def find_cd_drive() -> str:
    """Drive letter of a drive that holds an audio CD (.cda files)."""
    import ctypes
    for letter in string.ascii_uppercase:
        if ctypes.windll.kernel32.GetDriveTypeW(f"{letter}:\\") == 5:  # 5 = optical drive
            if list(Path(f"{letter}:\\").glob("*.cda")):
                return letter
    raise SystemExit("No audio CD found. Insert the disc or pass --drive D.")


def read_track_list(drive=None):
    """Returns (device_string, tracks). Track = {"number","start","end","duration"}."""
    drive = (drive or find_cd_drive()).rstrip(":\\").upper()
    last_err = ""
    for dev in (f"{drive}:", f"\\\\.\\{drive}:"):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-f", "libcdio", "-i", dev, "-show_chapters", "-of", "json"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            chapters = json.loads(r.stdout or "{}").get("chapters", [])
            tracks = []
            for i, ch in enumerate(chapters, start=1):
                start, end = float(ch["start_time"]), float(ch["end_time"])
                tracks.append({"number": i, "start": start, "end": end, "duration": end - start})
            if not tracks:
                raise SystemExit("Disc opened, but no track list was found.")
            return dev, tracks
        last_err = r.stderr.strip()
    raise SystemExit(f"FFmpeg could not open the disc:\n{last_err}")




if __name__ == "__main__":  # quick test: python read_tracks.py
    dev, tracks = read_track_list()
    print("Device:", dev)
    for t in tracks:
        print(f"Track {t['number']:02d}  {t['duration']:.0f}s")