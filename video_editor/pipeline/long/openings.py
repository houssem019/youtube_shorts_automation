"""Opening name and where the game leaves the book, from the Lichess opening tables (openings/*.tsv, CC0)."""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import chess
import chess.pgn

HERE = Path(__file__).parent / 'openings'


def _key(board: chess.Board) -> str:
    return board.epd()  # position + side to move + castling + en passant, no move counters


@lru_cache(maxsize=1)
def _book() -> dict[str, tuple[str, str]]:
    """{position: (eco, name)}; a longer line's name wins when two lines reach the same position."""
    book: dict[str, tuple[str, str, int]] = {}
    for f in sorted(HERE.glob('*.tsv')):
        for row in f.read_text(encoding='utf-8').splitlines()[1:]:
            parts = row.split('\t')
            if len(parts) < 3:
                continue
            eco, name, pgn = parts[:3]
            board = chess.Board()
            n = 0
            try:
                for tok in pgn.split():
                    if not tok[0].isdigit():  # skip move numbers like "1."
                        board.push_san(tok)
                        n += 1
            except ValueError:
                continue
            k = _key(board)
            if k not in book or book[k][2] < n:
                book[k] = (eco, name, n)
    return {k: (v[0], v[1]) for k, v in book.items()}


def detect(pgn_text: str) -> dict | None:
    """{"eco", "name", "family", "bookPly", "leftBy", "line"}: the deepest named position the game reached.
    bookPly = the last ply that is still a named book position; leftBy = the side whose next move left it."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return None
    book = _book()
    board = game.board()
    found, last_ply, sans = None, 0, []
    for i, mv in enumerate(game.mainline_moves(), 1):
        sans.append(board.san(mv))
        board.push(mv)
        hit = book.get(_key(board))
        if hit:
            found, last_ply = hit, i
        elif i - last_ply > 6:  # transpositions back into the book are rare after this
            break
    if not found:
        return None
    eco, name = found
    nxt = last_ply + 1
    line = ' '.join((f'{(j + 2) // 2}. ' if j % 2 == 0 else '') + s for j, s in enumerate(sans[:last_ply]))
    return dict(eco=eco, name=name, family=name.split(':')[0], bookPly=last_ply,
                leftBy='White' if nxt % 2 == 1 else 'Black', line=line)
