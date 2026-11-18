"""Step 7 - Display / log the result: print it and append a row to log.csv in the folder."""
import csv
from pathlib import Path


class ResultLog:
    def __init__(self, folder: Path):
        path = Path(folder) / "log.csv"
        is_new = not path.exists()
        self._file = open(path, "a", newline="", encoding="utf-8")
        self._csv = csv.writer(self._file)
        if is_new:
            self._csv.writerow(["track", "title", "artist", "album", "saved_as", "status"])
        self.path = path

    def add(self, track_number: int, result: dict, saved_as: str):
        if result["status"] == "identified":
            print(f"    Title : {result['title']}\n    Artist: {result['artist']}\n    Album : {result['album'] or '-'}")
        elif result["status"] == "error":
            print(f"    Error : {result['error']} -> saved as Unknown Artist")
        else:
            print("    Not identified -> saved as Unknown Artist")
        print(f"    Saved : {saved_as}")
        self._csv.writerow([track_number, result["title"], result["artist"], result["album"],
                            saved_as, result["status"]])
        self._file.flush()

    def close(self):
        self._file.close()