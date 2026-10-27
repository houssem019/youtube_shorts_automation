"""Built-in commentary writer. Used when Claude isn't available, or its script fails validation.

It is plainer than the Claude-written commentary but always valid and always factual: every line
comes from the engine analysis. Phrasing varies per game so videos don't all sound the same.
Like the Claude script it is a highlight: it starts a few moves before the key moments and fast-forwards
long quiet stretches, so the video stays around 45-50 seconds.
"""
from __future__ import annotations

import random

C = {'w': 'White', 'b': 'Black'}
OTHER = {'w': 'b', 'b': 'w'}


def _first_word(say: str) -> str:
    return say.split()[0].strip(',')


def _sq(uci: str | None):
    return (uci[:2], uci[2:4]) if uci else (None, None)


def _adv_words(cp: int) -> str:
    if cp >= 900:
        return 'completely winning'
    if cp >= 450:
        return 'up a whole piece'
    if cp >= 250:
        return 'clearly better'
    return 'a bit better'


def write(a: dict, s: dict, seed: int = 0) -> dict:
    rnd = random.Random(seed)
    pick = lambda options: rnd.choice(options)
    plies = a['plies']
    n = len(plies)
    last = plies[-1]
    winner = s['winner']
    loser = None if not winner else ('Black' if winner == 'White' else 'White')
    how = s['how']
    puzzle = s['puzzle']

    # ---------- hook ----------
    hook = []
    peak = s.get('peakForLoser')
    if loser and peak and peak['cp_for_loser'] >= 250:
        hook.append(dict(say=f"{loser} is {_adv_words(peak['cp_for_loser'])} in this game.", show='climax'))
        end = {'checkmate': 'still gets checkmated', 'resignation': 'still loses', 'time': 'still loses on time'}.get(how, 'still loses')
        hook.append(dict(say=f"And {loser} {end}.", show='final'))
    elif how == 'checkmate':
        hook.append(dict(say=pick([f"Checkmate in {s['totalMoves']} moves. Let's see how it happened.",
                                   f"This one ends with checkmate on move {s['totalMoves']}."]), show='final'))
    elif s['decisivePly']:
        d = plies[s['decisivePly'] - 1]
        hook.append(dict(say=pick([f"One move decided this game, and it was {C[d['color']]}'s.",
                                   f"Move {d['num']} is where this game was lost."]), show='climax'))
    else:
        hook.append(dict(say="A tense one today.", show='final'))

    # ---------- body: the stretch around the key moments ----------
    important = set()
    if s['decisivePly']:
        important.add(s['decisivePly'])
    anchor = s['decisivePly'] or n
    important |= {k for k in s['keyMoments'] if k >= anchor - 20}  # earlier key moments would make it too long
    tail = max(1, n - 3) if how == 'checkmate' else n
    important |= set(range(tail, n + 1))
    start = 1 if n <= 16 else max(1, min(important) - 6)
    hook.append(dict(say=pick(["Let's go back to the start.", "Back to move one.", "Let's rewind."]) if start == 1
                     else pick([f"Back to move {plies[start - 1]['num']}.", "Let's rewind a bit."]), show='rewind'))
    body = []
    fillers = ["Both sides keep developing.", "A few quiet moves.", "Some maneuvering in the middle.",
               "The position slowly builds up.", "Nothing dramatic just yet.", "Both players keep things tight."]
    trade_fillers = ["A few pieces come off the board.", "Some trades in the middle.", "Pieces start coming off."]
    skip_lines = ["A few moves later.", "Let's skip ahead.", "Fast forward a bit."]

    def add_filler(a_, z_):
        if z_ - a_ + 1 >= 7:  # long quiet stretch: fast-forward it
            body.append(dict(say=pick(skip_lines), skip=[a_, z_]))
            return
        caps = sum(1 for p in plies[a_ - 1:z_] if p['captured'])
        body.append(dict(say=pick(trade_fillers if caps >= 2 else fillers), spread=[a_, z_]))

    nxt = start
    if start == 1 and min(important) > 1:
        opening_end = min(min(important) - 1, 10)
        op = a.get('opening')
        body.append(dict(say=f"{op}." if op else pick(["The opening goes quietly.", "A normal start."]), spread=[1, opening_end]))
        nxt = opening_end + 1
    elif start > 1 and min(important) > start:
        body.append(dict(say=pick(["Here's where it starts.", "Watch this part.", "This is where it gets going."]),
                         spread=[start, min(important) - 1]))
        nxt = min(important)

    for k in sorted(p for p in important if p >= nxt):
        if k > nxt:
            add_filler(nxt, k - 1)
        p = plies[k - 1]
        is_puzzle = puzzle and puzzle['ply'] == k
        if is_puzzle:
            body.append(dict(say=f"{puzzle['toMove']} to move. There's a strong move here. Pause and find it.", puzzle=True))
        w0 = _first_word(p['say'])
        say = f"{C[p['color']]} plays {p['say']}."
        eff = []
        if p['mate']:
            body.append(dict(say=say[0].upper() + say[1:].replace(', checkmate', ''), moves=[dict(ply=k, word=w0)]))
            body.append(dict(say="Checkmate.", effects=[dict(type='slam', text='CHECKMATE', word='Checkmate')]))
        elif p['cls'] == 'blunder' or p['cls'] == 'mistake':
            mark = '??' if p['cls'] == 'blunder' else '?'
            body.append(dict(say=say, moves=[dict(ply=k, word=w0)]))
            to_sq = p['uci'][2:4]
            line = pick(["That's a blunder.", "That's the mistake.", "And that's a big error."]) if mark == '??' else pick(["Not the best.", "That's a slip.", "An inaccurate move."])
            if p.get('missedMate'):
                line, mark = "That misses a forced mate.", '?'
            eff = [dict(type='badge', square=to_sq, text=mark, word=line.split()[-1].strip('.'))]
            if p['bestSay'] and p['bestUci'] and not is_puzzle:
                f, t = _sq(p['bestUci'])
                line2 = f"{p['bestSay'].replace(', check', '').replace(', checkmate', '')} was the move."
                body.append(dict(say=line, effects=eff + [dict(type='evalbar', word=line.split()[0])]))
                body.append(dict(say=line2[0].upper() + line2[1:], effects=[dict(type='arrow', **{'from': f, 'to': t}, color='green', word=line2.split()[0])]))
            else:
                body.append(dict(say=line, effects=eff))
        else:
            body.append(dict(say=say, moves=[dict(ply=k, word=w0)]))
        nxt = k + 1
    if nxt <= n:
        add_filler(nxt, n)
    if how in ('resignation', 'time', 'abandonment') and loser:
        word = {'resignation': 'resigns', 'time': 'time'}.get(how, 'leaves')
        line = {'resignation': f"And {loser} resigns.", 'time': f"And {loser} runs out of time."}.get(how, f"And {loser} leaves the game.")
        body.append(dict(say=line, effects=[dict(type='slam', text={'resignation': 'RESIGNS', 'time': 'TIME!'}.get(how, 'GAME OVER'), word=word)]))
    elif how not in ('checkmate',) and not winner:
        body.append(dict(say="And it ends in a draw.", effects=[dict(type='slam', text='DRAW', word='draw')]))

    # ---------- outro ----------
    outro = []
    if puzzle:
        outro.append(dict(say=f"The move was {puzzle['answerSay'].replace(', check', '').replace(', checkmate', '')}.", show='puzzle_answer'))
        outro.append(dict(say=pick(["Did you find it?", "Did you spot it in time?", "Did you get it?"]), show='final'))
    else:
        outro.append(dict(say=pick(["What would you have played?", "Would you have seen that coming?"]), show='final'))
    return dict(title=_title(s, plies, loser, peak), hook=hook, body=body, outro=outro)


def _title(s: dict, plies: list, loser: str | None, peak: dict | None) -> str:
    """A short, factual title from the story (same facts the hook uses)."""
    how, moves = s['how'], s['totalMoves']
    if loser and peak and peak['cp_for_loser'] >= 250:
        return f"{loser} was winning and still lost"
    if how == 'checkmate':
        return f"Checkmate in {moves} moves"
    if s['decisivePly']:
        return f"Move {plies[s['decisivePly'] - 1]['num']} decided this game"
    if how == 'resignation' and loser:
        return f"{loser} resigns after {moves} moves"
    if how == 'time' and loser:
        return f"{loser} runs out of time on move {moves}"
    if not s['winner']:
        return f"A {moves}-move draw"
    return f"{s['winner']} wins in {moves} moves"
