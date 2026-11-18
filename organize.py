"""Step 6b - Group songs into a folder named after the common artist (e.g. Music/Chick Corea/)."""
import shutil
from collections import Counter
from pathlib import Path

from filename import safe_name
from write_disk import unique_path


def artists_of(result):
    if result["status"] != "identified":
        return []
    return [a.strip() for a in result["artist"].split(",") if a.strip()]


def pick_main_artist(results):
    """Artist on 2+ tracks and on at least half of the identified tracks, else None."""
    counts, spelling, identified = Counter(), {}, 0
    for r in results:
        names = {a.lower(): a for a in artists_of(r)}
        if names:
            identified += 1
        for key, original in names.items():
            counts[key] += 1
            spelling.setdefault(key, original)
    if not counts:
        return None
    key, n = counts.most_common(1)[0]
    return spelling[key] if n >= 2 and n * 2 >= identified else None


def existing_artist_folders(root: Path):
    return {p.name.lower(): p for p in root.iterdir() if p.is_dir()}


def target_folder(root: Path, result, main_artist, existing):
    lowered = [a.lower() for a in artists_of(result)]
    if main_artist and main_artist.lower() in lowered:
        return root / safe_name(main_artist)
    for a in lowered:  # artist folder from an earlier CD already exists
        if safe_name(a).lower() in existing:
            return existing[safe_name(a).lower()]
    return root


def move_into(src: Path, dest_folder: Path) -> Path:
    dest_folder.mkdir(parents=True, exist_ok=True)
    if src.parent == dest_folder:
        return src
    dest = unique_path(dest_folder, src.stem, src.suffix)
    shutil.move(str(src), str(dest))
    return dest