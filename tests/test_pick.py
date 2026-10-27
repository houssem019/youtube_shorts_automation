"""Checks the random game pick for both formats without making or uploading anything.
Run from the project root: python -m tests.test_pick"""
import io
import logging

import chess.pgn

from config import (CHESS_USERNAME, HISTORY_FILE, LONG_HISTORY_FILE, LONG_MAX_PLIES, LONG_MIN_PLIES,
                    LONG_TIME_CLASS)
from src.chess_api import _count_moves, get_random_unedited_game
from src.utils import get_game_id, load_history

logging.basicConfig(level=logging.INFO)


def check(fmt, history, **kw):
    pgn = get_random_unedited_game(CHESS_USERNAME, history, **kw)
    assert pgn, f"{fmt}: no game found"
    headers = chess.pgn.read_headers(io.StringIO(pgn))
    plies = _count_moves(pgn)
    game_id = get_game_id(pgn)
    print(f"{fmt}: {game_id} | {headers.get('TimeControl')} | {plies} plies | {headers.get('Termination')}")
    assert game_id not in history, f"{fmt}: picked a game that is already in its history"
    assert kw.get("min_plies", 0) <= plies <= kw["max_plies"], f"{fmt}: {plies} plies is out of range"
    return game_id


if __name__ == "__main__":
    shorts = load_history(HISTORY_FILE)
    longs = load_history(LONG_HISTORY_FILE)
    check("short", shorts, max_plies=100)
    for _ in range(3):
        check("long", longs, max_plies=LONG_MAX_PLIES, min_plies=LONG_MIN_PLIES, time_class=LONG_TIME_CLASS)
    # History exclusion: pretend one picked game was already made and pick again from a one-month pool
    picked = check("long", longs, max_plies=LONG_MAX_PLIES, min_plies=LONG_MIN_PLIES, time_class=LONG_TIME_CLASS)
    for _ in range(3):
        check("long", longs + [picked], max_plies=LONG_MAX_PLIES, min_plies=LONG_MIN_PLIES,
              time_class=LONG_TIME_CLASS)
    print("ok")
