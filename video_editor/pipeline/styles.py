"""Storytelling styles: each video tells its game a different way, so the channel doesn't feel repetitive.

A style sets what the writer is asked to do (hook, angle, pacing, which effects to lean on, the closing
question, the title pattern) and the video's look (colour palette, how the hook opens, the transition back to
move one, camera strength). The animations, eval bar, arrows, badges, captions and sounds are the same parts
in every look. Each style says which games it fits; `choose` picks the best-fitting style that wasn't used in
the last few uploads.
"""
from __future__ import annotations

from .analysis import win_pct

C = {'w': 'White', 'b': 'Black'}
AVOID_LAST = 3  # don't reuse a style from the last 3 uploaded videos (if another one fits)


def _clock(sec) -> str:
    sec = int(sec)
    return f'{sec // 60}:{sec % 60:02d}' if sec >= 60 else f'{sec} seconds'


# ---- scenario detectors: return the facts that make the style fit, or None if it doesn't ----

def _decisive(a, s):
    if not s['decisivePly']:
        return None
    p = a['plies'][s['decisivePly'] - 1]
    return [f"The turning point is ply {p['ply']} ({p['num']}{'.' if p['color'] == 'w' else '...'} {p['san']}, {C[p['color']]})."]


def _ending(a, s):
    return [f"The game ends by {s['how']} after {s['totalMoves']} moves."]


def _puzzle(a, s):
    z = s.get('puzzle')
    if not z:
        return None
    return [f"Puzzle: {z['toMove']} to move before ply {z['ply']}. The winning idea was {z['answerSay']}; {z['toMove']} played {z['playedSay']} instead."]


def _comeback(a, s):
    peak = s.get('peakForLoser')
    if not s['winner'] or not peak or peak['cp_for_loser'] < 200:
        return None
    loser = 'Black' if s['winner'] == 'White' else 'White'
    p = a['plies'][peak['ply'] - 1]
    return [f"{loser} (the side that lost) was ahead by {peak['cp_for_loser'] / 100:.1f} pawns after ply {p['ply']} (move {p['num']}), "
            f"about a {win_pct(peak['cp_for_loser']):.0f}% winning chance, and still lost."]


def _miniature(a, s):
    if not s['winner'] or s['totalMoves'] > 20:
        return None
    return [f"The whole game is only {s['totalMoves']} moves long."]


def _missed_mate(a, s):
    missed = [p for p in a['plies'] if p.get('missedMate') and p.get('bestSay')]
    if not missed:
        return None
    p = missed[0]
    return [f"On ply {p['ply']} (move {p['num']}) {C[p['color']]} had a forced mate starting with {p['bestSay']} "
            f"(engine line {p['bestLine']}) and played {p['say']} instead."] + \
           ([f"That happened {len(missed)} times in this game."] if len(missed) > 1 else [])


def _time_scramble(a, s):
    tail = [p for p in a['plies'][-12:] if p.get('clock') is not None]
    low = [p for p in tail if p['clock'] <= 20]
    if s['how'] != 'time' and not low:
        return None
    out = [f"Time control: {a.get('timeControl') or 'unknown'} (seconds per side, + increment if any)."]
    for c in ('w', 'b'):
        mine = [p for p in tail if p['color'] == c]
        if mine:
            q = min(mine, key=lambda p: p['clock'])
            out.append(f"{C[c]}'s lowest clock near the end: {_clock(q['clock'])} left after ply {q['ply']} (move {q['num']}).")
    if s['how'] == 'time':
        out.append('The game ends because a player runs out of time.')
    return out


def _underdog(a, s):
    w, b = a['white']['rating'], a['black']['rating']
    if not s['winner'] or not w or not b:
        return None
    win_r, lose_r = (w, b) if s['winner'] == 'White' else (b, w)
    if lose_r - win_r < 100:
        return None
    return [f"{s['winner']} is rated {win_r}, {lose_r - win_r} points below their opponent ({lose_r}), and wins."]


def _chaos(a, s):
    """The advantage (at least 1.5 pawns) changes hands 3 or more times."""
    leader, flips = None, []
    for p in a['plies']:
        if abs(p['cp']) < 150:
            continue
        side = 'w' if p['cp'] > 0 else 'b'
        if leader and side != leader:
            flips.append(p)
        leader = side
    if len(flips) < 3:
        return None
    ev = lambda p: 'forced mate' if p['mate'] or p['mateIn'] else f"{p['cp'] / 100:+.1f}"
    swings = '; '.join(f"ply {p['ply']} {C[p['color']]} {p['say']} (eval after: {ev(p)})" for p in flips[:8])
    return [f"The advantage changes hands {len(flips)} times in this game. The moves where it flips: {swings}."]


def _long_grind(a, s):
    if s['totalMoves'] < 40 or not s['decisivePly'] or s['decisivePly'] < 60:
        return None
    return [f"A long game: {s['totalMoves']} moves, and it is only decided late (ply {s['decisivePly']}), in the endgame."]


# ---- the style map ----
# score: how strongly the style should win when it fits (rarer, more specific stories score higher).

STYLES = [
    dict(id='missed_mate', name='The mate that got away', score=9, fits=_missed_mate,
         brief="""Angle: a forced checkmate was on the board and the player didn't see it.
Hook (show "climax"): open on the missed chance, not on the result. Make the viewer want to see the mate.
Body: start a few moves before that moment; when it comes, slow down, show the mating idea with a green arrow,
and badge the move that was played instead. Then skip to the finish.
Outro: ask the viewer which move they would have played there.
Title: about the missed mate (e.g. "Black had mate in 2 and played this"). Don't copy this example."""),
    dict(id='time_scramble', name='Race against the clock', score=8, fits=_time_scramble,
         brief="""Angle: the clock is a third player. Use the clock facts (say times as "eight seconds", "under a minute").
Hook (show "final"): lead with how little time was left; let the viewer wonder who survives it.
Body: start where the clocks get low; mention the time left once or twice so the tension rises. Skip quiet
stretches. Short lines near the end.
Outro: ask what the viewer does in a time scramble.
Title: about time pressure (e.g. "Eight seconds left and this happens"). Don't copy this example."""),
    dict(id='comeback', name='Winning, then not', score=8, fits=_comeback,
         brief="""Angle: the side that lost was clearly winning first. The story is how the advantage slipped away.
Hook (show "climax"): say who was winning and by how much, then hint that it doesn't last.
Body: start just before the losing side's best moment; say how good it was and use the evalbar effect. Then
slow down on the moves where the advantage drains away, with the evalbar again when it flips.
Outro: ask where the viewer thinks it went wrong.
Title: about the lost advantage (e.g. "Up a whole piece and still lost"). Don't copy this example."""),
    dict(id='puzzle_challenge', name='Find the move', score=7, fits=_puzzle,
         brief="""Angle: the viewer is a player in this video. One position has a winning move; challenge them to find it.
Hook (show "final"): set up the challenge directly ("There's one move in this game that wins. You get three
seconds."). Don't reveal the position or the answer in the hook.
Body: play the game toward the puzzle position with a little suspense; the puzzle line is required here.
Outro: reveal the answer (show "puzzle_answer"), say what was played instead, then ask how fast they found it.
Title: a challenge to the viewer, without the answer (e.g. "Can you find what White missed?"). Don't copy this example."""),
    dict(id='underdog', name='The underdog', score=7, fits=_underdog,
         brief="""Angle: the lower-rated player wins. Use the rating facts once in the hook, then let the chess speak.
Hook (show "final"): state the rating gap and ask who the viewer backs; the result comes at the end.
Body: point out the moment the favourite starts to go wrong, and give the underdog credit for good moves.
Outro: ask if ratings really matter at this level.
Title: about the rating gap (e.g. "100 points lower, didn't matter"). Don't copy this example."""),
    dict(id='chaos', name='Total chaos', score=6, fits=_chaos,
         brief="""Angle: a wild game where the advantage changes hands again and again. Keep count of the swings.
Hook (show "climax"): promise the viewer a messy, unpredictable game.
Body: react briefly to the biggest swings (two or three, there isn't time for all) with the evalbar effect;
badges "??" on blunders. Skip the stretches in between and keep a running count of the swings.
Outro: ask the viewer to count or rate the blunders.
Title: about the chaos (e.g. "Nobody wanted to win this game"). Don't copy this example."""),
    dict(id='miniature', name='Short and brutal', score=6, fits=_miniature,
         brief="""Angle: the game is over almost before it starts. Keep the whole video short and punchy.
Hook (show "final"): one short line about how fast it ended, then the rewind line.
Body: a miniature can be shown from move one, mostly with "spread"; explain the one idea that decided it.
Aim for the low end of the length.
Outro: a short question about the opening trap or mistake.
Title: about how fast it was (e.g. "Over in 14 moves"). Don't copy this example."""),
    dict(id='long_grind', name='The long grind', score=5, fits=_long_grind,
         brief="""Angle: a patient game that's only decided in the endgame. Respect the fight.
Hook (show "climax"): point at the endgame moment where it was finally decided.
Body: start in the endgame and say how long they've been fighting; skip quiet endgame moves; slow down at the
slip and explain the plan (arrows for king walks, passed pawns, the key square).
Outro: ask the viewer where they would have defended differently.
Title: about the endgame or the long fight (e.g. "40 moves of pressure, one slip"). Don't copy this example."""),
    dict(id='turning_point', name='The one move', score=3, fits=_decisive,
         brief="""Angle: one move decided the game. This is the classic format.
Hook (show "climax"): open on the decisive moment and challenge the viewer with it; don't say how it ends.
Body: start a few moves before the turning point, slow down on it, explain the idea and the better move.
Outro: ask what the viewer would have played.
Title: about the key move."""),
    dict(id='how_did_we_get_here', name='How did we get here?', score=2, fits=_ending,
         brief="""Angle: start at the end and make the viewer wonder how the game got there.
Hook (show "final"): describe the final position or the result as a question ("How does Black lose in 19 moves?").
Body: tell the game as the answer to that question; skip what doesn't explain it, slow down on what does.
Outro: ask the viewer which moment they think decided it.
Title: a question about the ending or the result."""),
]
BY_ID = {x['id']: x for x in STYLES}


# ---- looks ----
# palette: background gradient, board squares, accent (active caption word, countdown, headline), slam colour.
# opener: "still" (frozen board + zoom, the original look), "replay" (the moves into the key moment play in the
#   hook), "headline" (dimmed board + a big headline built from the game facts).
# transition: "tape" (REWIND tape effect, the original), "flash" (white flash, fast rewind), "clean" ("MOVE 1" label).
# zoom: multiplies how far the camera pushes in (1 = original).
PALETTES = {
    'midnight': dict(bg=['#1B2333', '#0C1018', '#06080C'], light='#E6E1D3', dark='#5E7C8A', accent='#FFD43B', slam='#FF4D4F'),
    'tournament': dict(bg=['#1A2B20', '#0B1510', '#050A07'], light='#EEEED2', dark='#769656', accent='#FFE45C', slam='#FF4D4F'),
    'walnut': dict(bg=['#2C2016', '#150F0A', '#090604'], light='#F0D9B5', dark='#B58863', accent='#FFB547', slam='#FF5A36'),
    'ice': dict(bg=['#132A40', '#091726', '#040B14'], light='#DEE3E6', dark='#8CA2AD', accent='#5CE1E6', slam='#FF4D6D'),
    'ember': dict(bg=['#2E1416', '#16090A', '#080304'], light='#ECDCC8', dark='#A86F5C', accent='#FF9F43', slam='#FFD43B'),
    'violet': dict(bg=['#251C38', '#120D1E', '#08060F'], light='#E9E4F3', dark='#8B7BB8', accent='#FFD43B', slam='#FF4D4F'),
}


def _headline_time(a, s):
    if s['how'] == 'time':
        return 'OUT OF TIME'
    clocks = [p['clock'] for p in a['plies'][-12:] if p.get('clock') is not None]
    if not clocks or min(clocks) > 20:
        return 'TIME TROUBLE'
    sec = int(min(clocks))
    return f"{sec} SECOND{'' if sec == 1 else 'S'} LEFT"


def _headline_chaos(a, s):
    facts = _chaos(a, s) or []
    n = next((int(w) for f in facts for w in f.split() if w.isdigit()), None)
    return f'{n} LEAD CHANGES' if n else 'TOTAL CHAOS'


LOOK = {
    'missed_mate': dict(palette='violet', opener='headline', transition='flash', zoom=1.2, headline=lambda a, s: 'MISSED MATE'),
    'time_scramble': dict(palette='midnight', opener='headline', transition='flash', zoom=1.35, headline=_headline_time),
    'comeback': dict(palette='walnut', opener='headline', transition='clean', zoom=1.0,
                     headline=lambda a, s: f"+{s['peakForLoser']['cp_for_loser'] / 100:.1f} AND LOST"),
    'puzzle_challenge': dict(palette='ice', opener='headline', transition='clean', zoom=1.0, headline=lambda a, s: 'FIND THE MOVE'),
    'underdog': dict(palette='tournament', opener='headline', transition='clean', zoom=1.0,
                     headline=lambda a, s: f"{abs(a['white']['rating'] - a['black']['rating'])} POINTS LOWER"),
    'chaos': dict(palette='ember', opener='replay', transition='flash', zoom=1.35, headline=_headline_chaos),
    'miniature': dict(palette='tournament', opener='replay', transition='flash', zoom=1.35, headline=lambda a, s: f"{s['totalMoves']} MOVES"),
    'long_grind': dict(palette='walnut', opener='replay', transition='tape', zoom=0.6, headline=None),
    'turning_point': dict(palette='midnight', opener='replay', transition='tape', zoom=1.0, headline=None),
    'how_did_we_get_here': dict(palette='ice', opener='still', transition='tape', zoom=1.0, headline=None),
}
DEFAULT_LOOK = dict(palette='midnight', opener='still', transition='tape', zoom=1.0, headline=None)  # the original look


def look_for(style_id: str | None, a: dict, s: dict) -> dict:
    """The look for a style (the original look for the built-in writer or an unknown style), with its headline text."""
    lk = dict(LOOK.get(style_id or '', DEFAULT_LOOK))
    text = None
    # a headline states a fact, so only when the game really fits the style (a style forced by hand may not)
    if lk['opener'] == 'headline' and lk.get('headline') and BY_ID[style_id]['fits'](a, s) is not None:
        try:
            text = lk['headline'](a, s)
        except Exception:  # noqa: BLE001  (a missing fact)
            text = None
    if lk['opener'] == 'headline' and not text:
        lk['opener'] = 'still'  # no true headline for this game: open with the frozen board instead
    lk['headline'] = text
    lk['colors'] = PALETTES[lk['palette']]
    return lk


def choose(a: dict, s: dict, recent: list[str], force: str | None = None) -> tuple[dict, list[str], str]:
    """Returns (style, style facts, reason). `recent` = style ids of the last uploads, newest last."""
    fitting = []
    for x in STYLES:
        f = x['fits'](a, s)
        if f is not None:
            fitting.append((x, f))
    if force:
        x = BY_ID[force]
        return x, x['fits'](a, s) or [], 'chosen by hand'
    recent = [r for r in recent if r]  # an upload recorded without a style doesn't count
    last = recent[-AVOID_LAST:]
    fresh = [(x, f) for x, f in fitting if x['id'] not in last]
    pool = fresh or [(x, f) for x, f in fitting if not recent or x['id'] != recent[-1]] or fitting

    def last_used(x):  # tie-break: the style used longest ago
        return max((i for i, r in enumerate(recent) if r == x['id']), default=-1)
    x, f = max(pool, key=lambda xf: (xf[0]['score'], -last_used(xf[0])))
    others = ', '.join(y['id'] for y, _ in fitting if y is not x)
    return x, f, f"fits this game; also fitting: {others or 'none'}; recent: {', '.join(last) or 'none'}"
