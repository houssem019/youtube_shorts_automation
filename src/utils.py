import json
import os
import logging
import io
import chess.pgn
from config import HISTORY_FILE

logger = logging.getLogger(__name__)

def load_history():
    """
    Loads the history of processed game IDs.
    """
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return []

def save_history(history):
    """
    Saves the history of processed game IDs.
    """
    try:
        with open(HISTORY_FILE, 'w') as f:
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

def get_game_metadata(pgn_string):
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
            "title": f"Chess Game #chess #chessgame #chesstactics #gothamchess #magnuscarlsen",
            "description": f""
        }
    except:
        return {"title": "Chess Game #chess #chessgame #chesstactics #gothamchess #magnuscarlsen", "description": ""}
