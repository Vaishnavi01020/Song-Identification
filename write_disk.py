"""Step 6 - Write to hard disk: give the saved track its final name (never overwrites)."""
from pathlib import Path


def unique_path(folder: Path, base: str, ext: str = ".wav") -> Path:
    p = folder / f"{base}{ext}"
    n = 2
    while p.exists():  # never overwrite: "Name (2).wav"
        p = folder / f"{base} ({n}){ext}"
        n += 1
    return p


def write_to_disk(temp_path: Path, folder: Path, base_name: str) -> Path:
    """Rename TrackNN.wav to its final name inside the folder."""
    dest = unique_path(folder, base_name, temp_path.suffix.lower() or ".wav")
    temp_path.rename(dest)
    return dest