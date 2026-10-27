"""Engine analysis of a whole game: evaluation, best move and move quality for every ply."""
from __future__ import annotations

import io
import math
import re

import chess
import chess.engine
import chess.pgn

PIECE_NAMES = {chess.PAWN: 'pawn', chess.KNIGHT: 'knight', chess.BISHOP: 'bishop', chess.ROOK: 'rook', chess.QUEEN: 'queen', chess.KING: 'king'}
MATE_CP = 10000


def win_pct(cp: int) -> float:
    """Lichess-style win probability (0-100) for the side the cp value favours."""
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def spoken(board: chess.Board, move: chess.Move) -> str:
    """How a commentator says a move: 'knight takes e5', 'castles', 'queen h7, checkmate'."""
    if board.is_castling(move):
        text = 'castles' if chess.square_file(move.to_square) == 6 else 'castles long'
    else:
        piece = board.piece_at(move.from_square)
        to = chess.square_name(move.to_square)
        cap = board.is_capture(move)
        if piece.piece_type == chess.PAWN:
            text = f"{chess.square_name(move.from_square)[0]} takes {to}" if cap else to
        else:
            text = f"{PIECE_NAMES[piece.piece_type]} {'takes ' if cap else ''}{to}"
        if move.promotion:
            text += f" promoting to a {PIECE_NAMES[move.promotion]}"
    board.push(move)
    if board.is_checkmate():
        text += ', checkmate'
    elif board.is_check():
        text += ', check'
    board.pop()
    return text


def _score(info) -> tuple[int, int | None]:
    s = info['score'].white()
    return s.score(mate_score=MATE_CP), s.mate()


def _pos(board: chess.Board) -> dict:
    return {chess.square_name(s): p.symbol() for s, p in board.piece_map().items()}


def opening_name(headers) -> str | None:
    url = headers.get('ECOUrl') or ''
    m = re.search(r'/openings/([^?#]+)', url)
    if not m:
        return headers.get('Opening')
    name = m.group(1).replace('-', ' ')
    name = re.sub(r'\s+\d.*$', '', name)  # drop move-sequence tails like "...3.exd5"
    return name.strip() or None


def analyse(pgn_text: str, stockfish_path: str, username: str | None = None, depth: int = 16, max_plies: int | None = None) -> dict:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError('Could not read PGN')
    h = game.headers
    board = game.board()
    moves = list(game.mainline_moves())
    if max_plies:
        moves = moves[:max_plies]

    user_color = None
    if username:
        if h.get('White', '').lower() == username.lower():
            user_color = 'w'
        elif h.get('Black', '').lower() == username.lower():
            user_color = 'b'

    clocks = []
    for node in game.mainline():
        clocks.append(node.clock())

    eng = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    try:
        info = eng.analyse(board, chess.engine.Limit(depth=depth))
        prev_cp, prev_mate = _score(info)
        prev_pv = info.get('pv', [])
        plies, positions = [], [_pos(board)]
        for i, mv in enumerate(moves, 1):
            turn = board.turn
            san = board.san(mv)
            say = spoken(board, mv)
            best = board.san(prev_pv[0]) if prev_pv else None
            best_line = board.variation_san(prev_pv[:6]) if prev_pv else ''
            best_say = spoken(board, prev_pv[0]) if prev_pv else None
            best_uci = prev_pv[0].uci() if prev_pv else None
            anim = [[chess.square_name(mv.from_square), chess.square_name(mv.to_square)]]
            if board.is_castling(mv):
                rook = {chess.G1: ('h1', 'f1'), chess.C1: ('a1', 'd1'), chess.G8: ('h8', 'f8'), chess.C8: ('a8', 'd8')}[mv.to_square]
                anim.append(list(rook))
            cap_sq = None
            cap_piece = None
            if board.is_capture(mv):
                cap = mv.to_square if not board.is_en_passant(mv) else mv.to_square + (-8 if turn else 8)
                cap_sq = chess.square_name(cap)
                cap_piece = board.piece_at(cap).symbol()
            mover_piece = board.piece_at(mv.from_square).symbol()
            fen_before = board.fen()
            board.push(mv)
            if board.is_checkmate():
                cp, mate, pv = (MATE_CP if turn else -MATE_CP), 0, []
            elif board.is_game_over():
                cp, mate, pv = 0, None, []
            else:
                info = eng.analyse(board, chess.engine.Limit(depth=depth))
                (cp, mate), pv = _score(info), info.get('pv', [])
            sign = 1 if turn == chess.WHITE else -1
            before = win_pct(sign * prev_cp)
            after = win_pct(sign * cp)
            wp_loss = before - after
            missed_mate = not board.is_checkmate() and prev_mate is not None and (prev_mate > 0) == (turn == chess.WHITE) and prev_mate != 0 and (mate is None or (mate > 0) != (turn == chess.WHITE))
            if san == best:
                cls = 'best'
            elif missed_mate or wp_loss >= 20:
                cls = 'blunder'
            elif wp_loss >= 10:
                cls = 'mistake'
            elif wp_loss >= 5:
                cls = 'inaccuracy'
            else:
                cls = 'good'
            king = chess.square_name(board.king(board.turn)) if board.is_check() else None
            plies.append(dict(
                ply=i, num=(i + 1) // 2, color='w' if turn else 'b', san=san, say=say, uci=mv.uci(), moves=anim,
                piece=mover_piece, captured=cap_sq, capturedPiece=cap_piece, check=king, mate=board.is_checkmate(),
                cp=cp, mateIn=mate, wpLoss=round(wp_loss, 1), cls=cls, missedMate=missed_mate,
                best=best, bestSay=best_say, bestUci=best_uci, bestLine=best_line, fen=board.fen(), fenBefore=fen_before,
                clock=clocks[i] if i < len(clocks) else None,
            ))
            positions.append(_pos(board))
            prev_cp, prev_mate, prev_pv = cp, mate, pv
    finally:
        eng.quit()

    def player(c):
        name = h.get('White' if c == 'w' else 'Black', '?')
        elo = h.get('WhiteElo' if c == 'w' else 'BlackElo')
        return dict(name=name, rating=int(elo) if elo and elo.isdigit() else None)

    return dict(
        white=player('w'), black=player('b'), userColor=user_color,
        result=h.get('Result', '*'), termination=h.get('Termination', ''), opening=opening_name(h),
        timeControl=h.get('TimeControl'), link=h.get('Link'), plies=plies, positions=positions,
    )
