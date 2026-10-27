"""Find the story in an analysed game: who won and how, the turning point, a puzzle moment."""
from __future__ import annotations

import re

from .analysis import win_pct

COLOR = {'w': 'White', 'b': 'Black'}


def _winner(a: dict) -> str | None:
    if a['plies'] and a['plies'][-1]['mate']:
        return a['plies'][-1]['color']
    return {'1-0': 'w', '0-1': 'b'}.get(a['result'])


def _how(a: dict) -> str:
    if a['plies'] and a['plies'][-1]['mate']:
        return 'checkmate'
    t = (a['termination'] or '').lower()
    for key, val in (('resign', 'resignation'), ('time', 'time'), ('abandon', 'abandonment'), ('stalemate', 'stalemate'),
                     ('repetition', 'repetition'), ('agreement', 'agreement'), ('insufficient', 'insufficient material'), ('50', '50-move rule')):
        if key in t:
            return val
    return 'draw' if a['result'] == '1/2-1/2' else 'unknown'


def find_story(a: dict) -> dict:
    plies = a['plies']
    n = len(plies)
    winner = _winner(a)
    loser = None if winner is None else ('b' if winner == 'w' else 'w')

    def wp_for(c, cp):
        return win_pct(cp if c == 'w' else -cp)

    # biggest mistakes, worst first
    errors = sorted([p for p in plies if p['cls'] in ('blunder', 'mistake')], key=lambda p: -p['wpLoss'])
    key_moments = sorted(errors[:3], key=lambda p: p['ply'])

    # the turning point: the loser's last big error before the game was lost for good
    decisive = None
    if loser:
        lost_errors = [p for p in plies if p['color'] == loser and p['cls'] in ('blunder', 'mistake')]
        for p in reversed(lost_errors):
            later = [wp_for(loser, q['cp']) for q in plies[p['ply'] - 1:]]
            if max(later) < 40:
                decisive = p
                break
        if not decisive and lost_errors:
            decisive = max(lost_errors, key=lambda p: p['wpLoss'])
    elif errors:
        decisive = errors[0]

    best_for_loser = None
    if loser:
        peak = max(plies, key=lambda p: (p['cp'] if loser == 'w' else -p['cp']))
        best_for_loser = dict(ply=peak['ply'], cp_for_loser=(peak['cp'] if loser == 'w' else -peak['cp']))

    # a "find the move" pause just before the decisive error, if a clearly better move existed
    puzzle = None
    if decisive and decisive['best'] and decisive['best'] != decisive['san'] and decisive['wpLoss'] >= 15:
        puzzle = dict(ply=decisive['ply'], toMove=COLOR[decisive['color']], answer=decisive['best'], answerSay=decisive['bestSay'],
                      line=decisive['bestLine'], played=decisive['san'], playedSay=decisive['say'])

    climax = n if plies and (plies[-1]['mate'] or (decisive is None)) else (decisive['ply'] if decisive else n)
    captures = [dict(ply=p['ply'], by=p['piece'], took=p['capturedPiece'], san=p['san']) for p in plies if p['captured']]
    return dict(
        winner=COLOR.get(winner) if winner else None, how=_how(a), totalMoves=(n + 1) // 2, plies=n,
        userColor=COLOR.get(a['userColor']) if a['userColor'] else None, opening=a['opening'],
        decisivePly=decisive['ply'] if decisive else None, keyMoments=[p['ply'] for p in key_moments], climaxPly=climax,
        peakForLoser=best_for_loser, puzzle=puzzle, captures=captures,
    )
