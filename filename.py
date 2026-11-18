"""Step 5 - Generate the file name.  Default: "{title} - {artist}"; unidentified: "Track07 - Unknown Artist"."""
import re


def check_format(name_format: str) -> bool:
    try:
        name_format.format(title="t", artist="a", album="b")
        return True
    except (KeyError, IndexError, ValueError):
        return False


def safe_name(text, limit=100):
    """Remove characters Windows/Linux don't allow in file names."""
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:limit].rstrip(" .")


def make_filename(result, track_number, name_format="{title} - {artist}"):
    """File name WITHOUT extension."""
    if result["status"] == "identified":
        return safe_name(name_format.format(
            title=result["title"], artist=result["artist"], album=result["album"] or "Unknown Album"))
    return f"Track{track_number:02d} - Unknown Artist"