"""Extra engine work for long videos: candidate moves at the key moments, tactics, game stats, and checking
the "what if" lines the writer wants to show."""
from __future__ import annotations

import math

import chess
import chess.engine

from ..analysis import MATE_CP, spoken, win_pct
from .motifs import hanging_after, line_swing, move_motifs

C = {'w': 'White', 'b': 'Black'}


def _cp(score: chess.engine.PovScore) -> tuple[int, int | None]:
    s = score.white()
    return s.score(mate_score=MATE_CP), s.mate()


def ev_text(cp: int, mate: int | None) -> str:
    if mate is not None and mate != 0:
        return f"{'White' if mate > 0 else 'Black'} mates in {abs(mate)}"
    return f"{cp / 100:+.1f}"


def key_plies(a: dict, s: dict, limit: int = 12) -> list[int]:
    """Moments worth a deep look: every mistake/blunder (worst first, capped), the turning point, the puzzle,
    the loser's best moment."""
    errs = sorted([p for p in a['plies'] if p['cls'] in ('blunder', 'mistake')], key=lambda p: -p['wpLoss'])
    keys = [p['ply'] for p in errs[:limit]]
    for k in (s.get('decisivePly'), (s.get('puzzle') or {}).get('ply'), (s.get('peakForLoser') or {}).get('ply')):
        if k and k not in keys:
            keys.append(k)
    return sorted(keys)


def candidates(eng, fen: str, depth: int = 18, multipv: int = 3) -> list[dict]:
    board = chess.Board(fen)
    infos = eng.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    out = []
    for info in infos:
        pv = info.get('pv') or []
        if not pv:
            continue
        cp, mate = _cp(info['score'])
        out.append(dict(san=board.san(pv[0]), say=spoken(board, pv[0]), uci=pv[0].uci(), cp=cp, mate=mate,
                        ev=ev_text(cp, mate), line=board.variation_san(pv[:8]),
                        lineSan=_sans(board, pv[:8])))
    return out


def _sans(board: chess.Board, pv) -> list[str]:
    b = board.copy()
    out = []
    for m in pv:
        out.append(b.san(m))
        b.push(m)
    return out


def deep_dive(a: dict, s: dict, stockfish: str, depth: int = 18, log=print) -> dict:
    """{ply: {candidates, playedMotifs, refutation, refutationMotifs, bestMotifs, hanging, swing}} for the key plies."""
    keys = key_plies(a, s)
    log(f'Looking deeper at {len(keys)} key moments...')
    out = {}
    eng = chess.engine.SimpleEngine.popen_uci(stockfish)
    try:
        for k in keys:
            p = a['plies'][k - 1]
            board = chess.Board(p['fenBefore'])
            played = board.parse_san(p['san'])
            cands = candidates(eng, p['fenBefore'], depth)
            d = dict(candidates=cands, playedMotifs=[m['text'] for m in move_motifs(board, played)])
            if cands and cands[0]['san'] != p['san']:
                best = board.parse_san(cands[0]['san'])
                d['bestMotifs'] = [m['text'] for m in move_motifs(board, best)]
                d['bestSwing'] = line_swing(p['fenBefore'], cands[0]['lineSan'])
            after = board.copy()
            after.push(played)
            d['hanging'] = [m['text'] for m in hanging_after(after)] if p['cls'] in ('blunder', 'mistake') else []
            if not after.is_game_over():
                ref = candidates(eng, after.fen(), depth, multipv=1)
                if ref:
                    d['refutation'] = ref[0]
                    rmove = after.parse_san(ref[0]['san'])
                    d['refutationMotifs'] = [m['text'] for m in move_motifs(after, rmove)]
                    d['refutationSwing'] = line_swing(after.fen(), ref[0]['lineSan'])
            out[k] = d
    finally:
        eng.quit()
    return out


def check_line(eng, fen: str, sans: list[str], depth: int = 16) -> dict:
    """Plays a "what if" line; returns {"ok", "error", "fens", "evals", "end", "swing", "motifs", "uci"}."""
    board = chess.Board(fen)
    fens, uci, motifs = [], [], []
    for i, san in enumerate(sans):
        try:
            mv = board.parse_san(san)
        except ValueError:
            return dict(ok=False, error=f'move {i + 1} "{san}" is not legal in that line')
        motifs += [m['text'] for m in move_motifs(board, mv)]
        uci.append(mv.uci())
        board.push(mv)
        fens.append(board.fen())
    evals = []
    for f in fens:
        b = chess.Board(f)
        if b.is_checkmate():
            evals.append((MATE_CP if not b.turn else -MATE_CP, 0))
        elif b.is_game_over():
            evals.append((0, None))
        else:
            info = eng.analyse(b, chess.engine.Limit(depth=depth))
            evals.append(_cp(info['score']))
    cp, mate = evals[-1] if evals else (0, None)
    return dict(ok=True, fens=fens, uci=uci, evals=evals, end=('checkmate' if mate == 0 else ev_text(cp, mate)),
                swing=line_swing(fen, sans, len(sans)), motifs=motifs)


# ---------- stats ----------

def _move_acc(loss: float) -> float:
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * max(0.0, loss)) - 3.1669))


def stats(a: dict) -> dict:
    """Accuracy (Lichess-style, from win% loss), error counts, the eval curve and time trouble per side."""
    out = {}
    for c in ('w', 'b'):
        mine = [p for p in a['plies'] if p['color'] == c]
        accs = [_move_acc(p['wpLoss']) for p in mine] or [100.0]
        harmonic = len(accs) / sum(1 / max(a_, 1.0) for a_ in accs)
        mean = sum(accs) / len(accs)
        clocks = [p['clock'] for p in mine if p.get('clock') is not None]
        low = next((p for p in mine if p.get('clock') is not None and p['clock'] < 60), None)
        out[c] = dict(accuracy=round((harmonic + mean) / 2, 1),
                      blunders=sum(p['cls'] == 'blunder' for p in mine), mistakes=sum(p['cls'] == 'mistake' for p in mine),
                      inaccuracies=sum(p['cls'] == 'inaccuracy' for p in mine),
                      lowestClock=round(min(clocks)) if clocks else None,
                      underAMinuteFromMove=low['num'] if low else None)
    curve = [30] + [max(-1500, min(1500, p['cp'])) for p in a['plies']]
    swings = [p['ply'] for p in a['plies'] if p['cls'] in ('blunder', 'mistake')]
    return dict(sides=out, curve=curve, swings=swings)


def phases(a: dict) -> dict:
    """Rough game phases by ply: opening until development/castling is mostly done, endgame once queens are
    off or little material is left."""
    n = len(a['plies'])
    end = None
    for p in a['plies']:
        board = chess.Board(p['fen'])
        heavy = sum(1 for x in board.piece_map().values() if x.piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT))
        if (not board.pieces(chess.QUEEN, True) and not board.pieces(chess.QUEEN, False)) or heavy <= 6:
            end = p['ply']
            break
    return dict(openingEnds=min(n, 20), endgameStarts=end)


def wp(cp: int, color: str) -> float:
    return win_pct(cp if color == 'w' else -cp)
