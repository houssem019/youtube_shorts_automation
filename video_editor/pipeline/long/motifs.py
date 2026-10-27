"""Simple tactic detectors (python-chess) so the commentary names real tactics instead of guessing.

Every detector looks at one move on one board and returns short facts in plain words, e.g.
"knight f5 forks the king on g7 and the queen on d6". Nothing here is a guess: each fact is a rule
checked on the board (attacks, pins, mate in one), so it can go straight into the writer's facts.
"""
from __future__ import annotations

import chess

NAME = {chess.PAWN: 'pawn', chess.KNIGHT: 'knight', chess.BISHOP: 'bishop', chess.ROOK: 'rook', chess.QUEEN: 'queen', chess.KING: 'king'}
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def _pc(board: chess.Board, sq: int) -> str:
    return f"{NAME[board.piece_type_at(sq)]} on {chess.square_name(sq)}"


def material(board: chess.Board, color: bool) -> int:
    return sum(VALUE[p.piece_type] for p in board.piece_map().values() if p.color == color and p.piece_type != chess.KING)


def _loose(board: chess.Board, sq: int, attacker_value: int) -> bool:
    """A target worth attacking: undefended, or worth more than the attacker."""
    p = board.piece_at(sq)
    return p.piece_type == chess.KING or VALUE[p.piece_type] > attacker_value or not board.attackers(p.color, sq)


def move_motifs(board: chess.Board, move: chess.Move) -> list[dict]:
    """Tactics created by `move` on `board` (the position before it). Returns [{name, text, squares}]."""
    out: list[dict] = []
    me = board.turn
    piece = board.piece_at(move.from_square)
    if piece is None:
        return out
    who = NAME[piece.piece_type]
    to = move.to_square
    captured = board.piece_at(to) if not board.is_en_passant(move) else chess.Piece(chess.PAWN, not me)
    defended_before = bool(board.attackers(not me, to)) if captured else False
    before_attacks = {s: board.attacks(s) for s in board.pieces(chess.BISHOP, me) | board.pieces(chess.ROOK, me) | board.pieces(chess.QUEEN, me)}
    pinned_before = {s for s in chess.SquareSet(board.occupied_co[not me]) if board.is_pinned(not me, s)}
    after = board.copy()
    after.push(move)

    if after.is_checkmate():
        return [dict(name='MATE', text=f"{who} {chess.square_name(to)} is checkmate", squares=[chess.square_name(to)])]

    if captured and (not defended_before or VALUE[captured.piece_type] > VALUE[piece.piece_type]):
        why = 'it was undefended' if not defended_before else f'it is worth more than the {who}'
        out.append(dict(name='WINS MATERIAL', text=f"{who} takes the {NAME[captured.piece_type]} on {chess.square_name(to)}; {why}",
                        squares=[chess.square_name(to)]))

    # fork: the moved piece attacks two or more worthwhile targets (counting the king when it gives check)
    if not after.is_attacked_by(not me, to) or piece.piece_type in (chess.PAWN, chess.KNIGHT):
        targets = [s for s in after.attacks(to) if after.color_at(s) == (not me) and _loose(after, s, VALUE[piece.piece_type])]
        if len(targets) >= 2:
            names = ' and the '.join(_pc(after, s) for s in sorted(targets, key=lambda s: -VALUE[after.piece_type_at(s)])[:2])
            out.append(dict(name='FORK', text=f"{who} {chess.square_name(to)} forks the {names}",
                            squares=[chess.square_name(to)] + [chess.square_name(s) for s in targets[:2]]))

    # pin: an enemy piece is newly pinned to its king by the moved piece
    for s in chess.SquareSet(after.occupied_co[not me]):
        if s in pinned_before or after.piece_type_at(s) == chess.KING or not after.is_pinned(not me, s):
            continue
        king = after.king(not me)
        if s in after.attacks(to) and king is not None and king in chess.SquareSet(chess.ray(to, s)):
            out.append(dict(name='PIN', text=f"{who} {chess.square_name(to)} pins the {_pc(after, s)} to the king",
                            squares=[chess.square_name(to), chess.square_name(s)]))
            break

    # skewer: a slider attacks the king or queen, and right behind it on the same line sits another piece
    if piece.piece_type in SLIDERS:
        for s in after.attacks(to):
            if after.color_at(s) != (not me) or after.piece_type_at(s) not in (chess.KING, chess.QUEEN):
                continue
            df = (chess.square_file(s) > chess.square_file(to)) - (chess.square_file(s) < chess.square_file(to))
            dr = (chess.square_rank(s) > chess.square_rank(to)) - (chess.square_rank(s) < chess.square_rank(to))
            f, r = chess.square_file(s) + df, chess.square_rank(s) + dr
            while 0 <= f < 8 and 0 <= r < 8:
                b = chess.square(f, r)
                if after.piece_at(b) is not None:
                    if after.color_at(b) == (not me) and after.piece_type_at(b) != chess.PAWN:
                        out.append(dict(name='SKEWER', text=f"{who} {chess.square_name(to)} skewers the {_pc(after, s)} and the {_pc(after, b)} behind it",
                                        squares=[chess.square_name(to), chess.square_name(s), chess.square_name(b)]))
                    break
                f, r = f + df, r + dr

    # discovered attack/check: another of our sliders now hits something big that it didn't before
    for s, old in before_attacks.items():
        if s == move.from_square:
            continue
        new = after.attacks(s) & ~old
        for t in new:
            if after.color_at(t) == (not me) and after.piece_type_at(t) in (chess.KING, chess.QUEEN, chess.ROOK):
                kind = 'discovered check' if after.piece_type_at(t) == chess.KING else 'discovered attack'
                out.append(dict(name='DISCOVERY', text=f"moving the {who} opens a {kind}: the {_pc(after, s)} now hits the {_pc(after, t)}",
                                squares=[chess.square_name(s), chess.square_name(t)]))
                break

    # mate threat: if the opponent passed, we would have mate in one
    if not after.is_check():
        threat = after.copy()
        threat.push(chess.Move.null())
        for m in threat.legal_moves:
            threat.push(m)
            mate = threat.is_checkmate()
            threat.pop()
            if mate:
                king = after.king(not me)
                back = king is not None and chess.square_rank(king) in (0, 7)
                kind = 'a back-rank mate' if back and threat.piece_type_at(m.from_square) in (chess.ROOK, chess.QUEEN) else 'mate'
                out.append(dict(name='MATE THREAT', text=f"threatens {kind} with {threat.san(m)}",
                                squares=[chess.square_name(m.from_square), chess.square_name(m.to_square)]))
                break
    return out


def hanging_after(board: chess.Board) -> list[dict]:
    """Pieces of the side that just moved which the opponent (to move) can simply take for free."""
    out = []
    victim = not board.turn
    for s in chess.SquareSet(board.occupied_co[victim]):
        t = board.piece_type_at(s)
        if t in (chess.KING, chess.PAWN) or not board.is_attacked_by(board.turn, s):
            continue
        cheapest = min(VALUE[board.piece_type_at(a)] for a in board.attackers(board.turn, s))
        if not board.attackers(victim, s) or cheapest < VALUE[t]:
            out.append(dict(name='HANGING', text=f"the {_pc(board, s)} is left {'undefended' if not board.attackers(victim, s) else 'attacked by a cheaper piece'}",
                            squares=[chess.square_name(s)]))
    return out


def line_swing(fen: str, sans: list[str], plies: int = 6) -> str | None:
    """Plain words for the material change at the end of a line, from the first mover's view."""
    board = chess.Board(fen)
    me = board.turn
    m0 = material(board, me) - material(board, not me)
    try:
        for s in sans[:plies]:
            board.push_san(s)
    except ValueError:
        return None
    if board.is_checkmate():
        return 'ends in checkmate'
    d = material(board, me) - material(board, not me) - m0
    if abs(d) < 2:
        return None
    what = {2: 'two pawns', 3: 'a piece', 4: 'a piece and a pawn', 5: 'a rook', 6: 'a rook and a pawn'}.get(abs(d), f'{abs(d)} points of material')
    return f"{'wins' if d > 0 else 'loses'} {what} by the end of the line"
