#!/usr/bin/env python3
"""
Rip a CD, identify every song, rename it, and group it by artist.

    python main.py                       (a window opens: choose the folder)
    python main.py --folder Music
    python main.py --folder Music --drive D: --workers 6 --timeout 300

Steps: read_tracks -> read_audio -> save_wav -> identify -> filename -> write_disk/organize -> log
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from acr_client import ACRSetupError
from read_tracks import read_track_list
from save_wav import rip_all
from identify import analyse_track
from filename import check_format, make_filename
from write_disk import write_to_disk
from organize import existing_artist_folders, move_into, pick_main_artist, target_folder
from log import ResultLog
from pick_folder import pick_folder


def main():
    ap = argparse.ArgumentParser(description="Rip a CD, name every song, group by artist.")
    ap.add_argument("--folder", help="main music folder (a folder chooser opens if you leave it out)")
    ap.add_argument("--drive", default=None, help="CD drive (default: auto-detect)")
    ap.add_argument("--name-format", default="{title} - {artist}",
                    help='file name pattern with {title} {artist} {album} (default "{title} - {artist}")')
    ap.add_argument("--workers", type=int, default=4, help="songs identified at the same time (default 4)")
    ap.add_argument("--timeout", type=int, default=180,
                    help="skip a track that takes longer than this many seconds to read (default 180)")
    ap.add_argument("--no-group", action="store_true", help="do not create artist folders")
    args = ap.parse_args()

    if not check_format(args.name_format):
        sys.exit('Bad --name-format. Use only {title}, {artist} and {album}.')

    if args.folder:
        folder = Path(args.folder)
    else:
        print("Choose the folder where the songs will be saved...")
        folder = pick_folder("Choose the folder to store the songs")
        if folder is None:
            sys.exit("No folder chosen. Stopped.")
    folder.mkdir(parents=True, exist_ok=True)

    device, tracks = read_track_list(args.drive)                                  # step 1
    print(f"Found {len(tracks)} tracks. Working in '{folder}'.\n")

    # Steps 2-4: rip track by track; each finished track is identified in the background
    results, futures = {}, {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        def submit(n, path):
            futures[pool.submit(analyse_track, path)] = n

        ripped = rip_all(device, tracks, folder, on_ready=submit, timeout=args.timeout)   # steps 2-3
        if not ripped:
            sys.exit("No tracks could be read from the CD.")
        missed = sorted({t["number"] for t in tracks} - {n for n, _ in ripped})
        if missed:
            print(f"\nSkipped (not read): {', '.join(f'Track{n:02d}' for n in missed)} "
                  "- run again later to retry them.")
        print(f"\nRipped {len(ripped)}/{len(tracks)} tracks. Finishing identification...\n")
        try:
            for fut in as_completed(futures):                                     # step 4
                n = futures[fut]
                results[n] = r = fut.result()
                label = f"{r['title']} - {r['artist']}" if r["status"] == "identified" else r["status"]
                print(f"[{len(results)}/{len(ripped)}] Track{n:02d}: {label}")
        except ACRSetupError as e:
            for f in futures:
                f.cancel()
            sys.exit(f"\nStopped: {e}\n(The ripped tracks are still in '{folder}'; run again to continue.)")

    # Steps 5-7: rename in the same folder, group by the common artist, log
    main_artist = None if args.no_group else pick_main_artist(list(results.values()))
    if main_artist:
        print(f"\nCommon artist on this CD: {main_artist} -> folder '{main_artist}'")
    existing = existing_artist_folders(folder)

    print()
    log = ResultLog(folder)
    try:
        for n, path in ripped:
            result = results[n]
            base = make_filename(result, n, args.name_format)                     # step 5
            renamed = write_to_disk(path, folder, base)                           # step 6
            dest_folder = folder if args.no_group else target_folder(folder, result, main_artist, existing)
            final = move_into(renamed, dest_folder)
            print(f"Track{n:02d}")
            log.add(n, result, str(final.relative_to(folder)))                    # step 7
    finally:
        log.close()

    print(f"\nDone. Songs are in '{folder}', log in '{log.path}'.")


if __name__ == "__main__":
    main()