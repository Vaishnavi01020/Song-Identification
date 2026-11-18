"""Step 4 - Find out which song a saved track is (ACRCloud) and clean the name."""
import re

from acr_client import ACRSetupError, identify_track


def clean_title(title):
    """Remove clutter such as (Remastered), [Live], '- From <film>'."""
    t = re.sub(r"\s*[\(\[].*?[\)\]]", "", title)
    t = re.sub(r"\s*-\s*(remaster(ed)?|live|from)\b.*$", "", t, flags=re.I)
    return t.strip()


def best_name(candidates):
    """(title, artist) from the best candidate, or (None, None)."""
    if not candidates:
        return None, None
    best = candidates[0]
    title, artist = clean_title(best["title"]), ", ".join(best["artists"][:2])
    return (title, artist) if title and artist else (None, None)


def analyse_track(path):
    """Returns {"title","artist","album","status","error"}; status = identified | unknown | error.
    Never raises for one bad track, only for setup problems."""
    try:
        candidates = identify_track(path)
    except ACRSetupError:
        raise  # missing keys / ffmpeg: stop the whole run
    except Exception as e:  # network, quota, unreadable file...
        return {"title": "", "artist": "", "album": "", "status": "error", "error": str(e)}

    title, artist = best_name(candidates)
    if title:
        return {"title": title, "artist": artist, "album": candidates[0].get("album") or "",
                "status": "identified", "error": None}
    return {"title": "", "artist": "", "album": "", "status": "unknown", "error": None}