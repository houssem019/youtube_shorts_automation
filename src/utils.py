import json
import os
import logging
import io
import chess.pgn
from config import HISTORY_FILE

logger = logging.getLogger(__name__)

def load_history(path=HISTORY_FILE):
    """
    Loads the history of processed game IDs (Shorts by default; long videos have their own file).
    """
    if not os.path.exists(path):
        return []

    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return []

def save_history(history, path=HISTORY_FILE):
    """
    Saves the history of processed game IDs.
    """
    try:
        with open(path, 'w') as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving history: {e}")

def get_game_id(pgn_string):
    """
    Extracts a unique identifier from the PGN.
    """
    try:
        pgn = io.StringIO(pgn_string)
        headers = chess.pgn.read_headers(pgn)
        # Chess.com PGNs usually have a Link header
        if "Link" in headers:
            return headers["Link"]

        # Fallback: Date + Time + White + Black
        date = headers.get("Date", "Unknown")
        time = headers.get("Time", "Unknown")
        white = headers.get("White", "Unknown")
        black = headers.get("Black", "Unknown")
        return f"{date}_{time}_{white}_{black}"

    except Exception as e:
        logger.error(f"Error extracting game ID: {e}")
        return None

HASHTAGS = "#chess #chessgame #chesstactics"
YOUTUBE_TITLE_LIMIT = 100


def make_title(story_title=None):
    """Story title (written by the video editor) + the fixed hashtags; "Chess Game" when there is none or it won't fit."""
    if story_title:
        story_title = " ".join(story_title.replace("#", "").replace("<", "").replace(">", "").split())
    if not story_title or len(f"{story_title} {HASHTAGS}") > YOUTUBE_TITLE_LIMIT:
        story_title = "Chess Game"
    return f"{story_title} {HASHTAGS}"


LONG_TITLE_MAX = 70


def _timestamp(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 \
        else f"{seconds // 60}:{seconds % 60:02d}"


def get_long_metadata(pgn_string, edited):
    """Title, description (summary, YouTube chapters, opening, game link, hashtags) and tags of a long video.
    `edited` is what editor_bridge.make_long_video returned."""
    title = " ".join((edited.get("title") or "").replace("<", "").replace(">", "").split())
    if not title or len(title) > LONG_TITLE_MAX:
        title = "Chess Game Analysis"
    lines = []
    if edited.get("summary"):
        lines += [edited["summary"], ""]
    chapters = edited.get("chapters") or []
    # YouTube only shows chapters when the first starts at 0:00 and there are at least 3 of 10 s or more.
    if len(chapters) >= 3 and chapters[0]["t"] == 0:
        lines += [f"{_timestamp(c['t'])} {c['title']}" for c in chapters] + [""]
    if edited.get("opening"):
        lines.append(f"Opening: {edited['opening']}")
    try:
        link = chess.pgn.read_headers(io.StringIO(pgn_string)).get("Link")
    except Exception:
        link = None
    if link:
        lines.append(f"Game: {link}")
    lines += ["", HASHTAGS]
    tags = ["chess", "chess game", "chess analysis", "chess tactics", "chess opening", "rapid chess"]
    if edited.get("opening"):
        tags.append(edited["opening"].split(":")[0])
    return {"title": title, "description": "\n".join(lines).strip(), "tags": tags}


def get_game_metadata(pgn_string, story_title=None):
    """
    Extracts metadata for video title/description.
    """
    try:
        pgn = io.StringIO(pgn_string)
        headers = chess.pgn.read_headers(pgn)
        white = headers.get("White", "?")
        black = headers.get("Black", "?")
        result = headers.get("Result", "*")
        return {
            "white": white,
            "black": black,
            "result": result,
            "title": make_title(story_title),
            "description": f""
        }
    except:
        return {"title": make_title(story_title), "description": ""}
