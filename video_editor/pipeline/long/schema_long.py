"""The long-video script format and its validator.

A script is JSON:
{
  "title":   str,     # YouTube title, max 70 characters
  "thumb":   str,     # 2-4 big words for the thumbnail and the cold open, max 24 characters
  "summary": str,     # 1-3 sentences for the video description
  "chapters": [
    {"kind": "cold_open", "lines": [Line with "show"]},            # first: 1-3 lines over a key position
    {"kind": "game", "title": str, "lines": [Line]},                # 3-6 chapters that walk through the game
    {"kind": "lessons", "title": str, "lines": [Line with "show"]}, # 2-4 lessons, one "lesson" card each
    {"kind": "outro", "lines": [Line with "show"]}                  # last: 1-2 short closing lines
  ]
}
Line = {"say": str,
        # at most one of these (none = talk over the position on screen):
        "moves":     [{"ply": int, "word": str}],     # a game move lands when that word is spoken
        "spread":    [first_ply, last_ply],            # play a run of game moves across the line
        "skip":      [first_ply, last_ply],            # fast-forward a run of quiet game moves
        "variation": {"from": ply, "san": [str], "words": [str]},  # "what if": instead of game ply `from`,
                     # play these SAN moves from the position before it. "words" (optional, one per move)
                     # anchors each move to a spoken word; else they spread across the line.
                     # {"continue": true, "san": [...]} goes on from the end of the previous variation.
        "show":      int | "final",                    # a still game position (after that ply; 0 = start)
        "think":     bool,                             # after this line: 5-second "pause and find it" timer
        "card":      Card,                             # a panel next to the board, starting with this line
        "effects":   [Effect]}
Card = {"type": "opening", "ideas": [str]}             # opening name/ECO filled in; 2-3 ideas, max 6 words each
     | {"type": "ideas", "heading": str, "points": [str]}   # a plan or the ideas of a position, 2-3 points
     | {"type": "candidates", "ply": int}              # the engine's top 3 moves before that game ply
     | {"type": "lesson", "text": str}                 # lessons chapter only, max 8 words
     | {"type": "stats"} | {"type": "graph"}           # accuracy/error counts, or the eval graph of the game
Effect = {"type": "arrow", "from": sq, "to": sq, "color": "red|green|orange", "word": str, "hold": int}
       | {"type": "badge", "square": sq, "text": "??|?|?!|!|!!|#", "word": str, "hold": int}
       | {"type": "ring", "square": sq, "word": str} | {"type": "zoom", "square": sq, "word": str, "hold": int}
       | {"type": "highlight", "squares": [sq], "color": "red|green|orange", "word": str}
       | {"type": "motif", "name": "FORK|PIN|SKEWER|DISCOVERY|HANGING|MATE THREAT|BACK RANK|TRAPPED|OVERLOADED",
          "square": sq, "targets": [sq], "word": str}
       | {"type": "evalbar", "word": str} | {"type": "slam", "text": str, "word": str}
The game chapters play every game ply from 1 to the last exactly once, in order (moves / spread / skip).
Key plies (turning point, puzzle, last move) are played with "moves". A variation may only start from a game
position already reached (from <= the next game ply to play).
"""
from __future__ import annotations

import re

import chess

from ..script_schema import SQ, has_word, norm  # noqa: F401  (norm is re-exported for the timeline)

TITLE_MAX = 70
THUMB_MAX = 24
COLORS = {'red', 'green', 'orange'}
BADGES = {'??', '?', '!', '!!', '#', '?!'}
MOTIFS = {'FORK', 'PIN', 'SKEWER', 'DISCOVERY', 'HANGING', 'MATE THREAT', 'BACK RANK', 'TRAPPED', 'OVERLOADED',
          'DEFLECTION', 'DOUBLE ATTACK', 'REMOVING THE DEFENDER', 'ZWISCHENZUG', 'PROMOTION'}
CARDS = {'opening', 'ideas', 'candidates', 'lesson', 'stats', 'graph'}
WORDS = (850, 1350)  # 5-9 minutes of narration at the long-video pace
MAX_LINE_WORDS = 45
MAX_THINKS = 3


def word_count(script: dict) -> int:
    return sum(len(x.get('say', '').split()) for ch in script.get('chapters', []) for x in ch.get('lines', []))


def lines(script: dict):
    """(chapter index, line index, chapter, line) for every line."""
    for ci, ch in enumerate(script.get('chapters', [])):
        for li, x in enumerate(ch.get('lines', [])):
            yield ci, li, ch, x


def validate(script: dict, a: dict, key_plies: set[int] | None = None, check_length: bool = True) -> list[str]:
    errs: list[str] = []
    if not isinstance(script, dict):
        return ['script is not an object']
    plies = a['plies']
    n = len(plies)
    for k, mx in (('title', TITLE_MAX), ('thumb', THUMB_MAX)):
        v = script.get(k)
        if not isinstance(v, str) or not v.strip():
            errs.append(f'"{k}" must be a non-empty string')
        elif len(v.strip()) > mx:
            errs.append(f'"{k}" is {len(v.strip())} characters, max {mx}')
        elif re.search(r'[#<>]', v):
            errs.append(f'"{k}" must not contain #, < or >')
    if not isinstance(script.get('summary'), str) or not script['summary'].strip():
        errs.append('"summary" must be a non-empty string')
    chs = script.get('chapters')
    if not isinstance(chs, list) or len(chs) < 4:
        return errs + ['"chapters" must be a list: cold_open, 3-6 game chapters, lessons, outro']
    kinds = [c.get('kind') for c in chs]
    if kinds[0] != 'cold_open':
        errs.append('the first chapter must be kind "cold_open"')
    if kinds[-1] != 'outro':
        errs.append('the last chapter must be kind "outro"')
    if kinds[-2] != 'lessons':
        errs.append('the chapter before the outro must be kind "lessons"')
    games = [c for c in chs if c.get('kind') == 'game']
    if not 3 <= len(games) <= 6:
        errs.append(f'there are {len(games)} game chapters; use 3-6')
    if kinds[1:-2] != ['game'] * (len(chs) - 3):
        errs.append('between the cold open and the lessons, every chapter must be kind "game"')
    for i, c in enumerate(chs):
        if c.get('kind') in ('game', 'lessons') and (not isinstance(c.get('title'), str) or not c['title'].strip() or len(c['title']) > 28):
            errs.append(f'chapter {i} ({c.get("kind")}) needs a "title" of at most 28 characters')
        if not isinstance(c.get('lines'), list) or not c['lines']:
            errs.append(f'chapter {i} has no lines')
    if errs:
        return errs

    expected = 1           # next game ply to play
    var_end: str | None = None  # FEN at the end of the last variation (for "continue")
    skipped: set[int] = set()
    played: set[int] = set()
    thinks = 0
    for ci, li, ch, x in lines(script):
        where = f'chapters[{ci}].lines[{li}]'
        kind = ch['kind']
        say = x.get('say', '')
        if not isinstance(say, str) or not say.strip():
            errs.append(f'{where} has no "say"')
            continue
        if len(say.split()) > MAX_LINE_WORDS:
            errs.append(f'{where} is {len(say.split())} words; max {MAX_LINE_WORDS} per line (split it)')
        modes = [k for k in ('moves', 'spread', 'skip', 'variation', 'show') if x.get(k) is not None and x.get(k) != []]
        if len(modes) > 1:
            errs.append(f'{where}: use only one of moves / spread / skip / variation / show (has {modes})')
        if kind in ('cold_open', 'lessons', 'outro'):
            if 'show' not in modes:
                errs.append(f'{where}: lines in the {kind} chapter need "show" (a ply number or "final")')
            if set(modes) - {'show'}:
                errs.append(f'{where}: the {kind} chapter can only use "show"')
        elif 'show' in modes:
            errs.append(f'{where}: "show" is only for the cold open, lessons and outro')
        if 'show' in modes:
            v = x['show']
            if not (v == 'final' or (isinstance(v, int) and 0 <= v <= n)):
                errs.append(f'{where}: show must be "final" or a ply 0-{n}')
        for k in ('spread', 'skip'):
            if k in modes:
                rng = x[k]
                if not (isinstance(rng, list) and len(rng) == 2 and all(isinstance(v, int) for v in rng)):
                    errs.append(f'{where}: {k} must be [first_ply, last_ply]')
                    continue
                lo, hi = rng
                if lo != expected or hi < lo or hi > n:
                    errs.append(f'{where}: {k} {rng} should start at ply {expected} (and end by ply {n})')
                if k == 'skip':
                    skipped |= set(range(lo, hi + 1))
                played |= set(range(lo, hi + 1))
                expected = max(expected, hi + 1)
        if 'moves' in modes:
            for m in x['moves']:
                if m.get('ply') != expected:
                    errs.append(f'{where}: move ply {m.get("ply")} out of order, expected {expected}')
                if not has_word(say, str(m.get('word', ''))):
                    errs.append(f'{where}: move word {m.get("word")!r} is not in the line')
                if isinstance(m.get('ply'), int):
                    played.add(m['ply'])
                expected = max(expected, (m.get('ply') or 0) + 1)
        if 'variation' in modes:
            v = x['variation']
            sans = v.get('san') if isinstance(v, dict) else None
            if not isinstance(sans, list) or not sans or not all(isinstance(s, str) for s in sans):
                errs.append(f'{where}: variation needs "san": a list of moves')
            else:
                if v.get('continue'):
                    fen = var_end
                    if fen is None:
                        errs.append(f'{where}: "continue" needs a variation in the line before it')
                else:
                    frm = v.get('from')
                    if not isinstance(frm, int) or not 1 <= frm <= n:
                        errs.append(f'{where}: variation "from" must be a game ply 1-{n}')
                        fen = None
                    elif frm > expected:
                        errs.append(f'{where}: variation from ply {frm} starts after the game position on screen '
                                    f'(the next game ply to play is {expected}); play the game up to it first')
                        fen = None
                    else:
                        fen = plies[frm - 1]['fenBefore']
                if fen:
                    board = chess.Board(fen)
                    for i, san in enumerate(sans):
                        try:
                            board.push_san(san)
                        except ValueError:
                            side = 'White' if board.turn else 'Black'
                            errs.append(f'{where}: variation move {i + 1} "{san}" is not legal ({side} to move, FEN {board.fen()})')
                            break
                    else:
                        var_end = board.fen()
                ws = v.get('words')
                if ws is not None:
                    if not isinstance(ws, list) or len(ws) != len(sans):
                        errs.append(f'{where}: variation "words" needs one word per move ({len(sans)})')
                    else:
                        for w in ws:
                            if not has_word(say, str(w)):
                                errs.append(f'{where}: variation word {w!r} is not in the line')
        if x.get('think'):
            thinks += 1
        card = x.get('card')
        if card is not None:
            t = card.get('type') if isinstance(card, dict) else None
            if t not in CARDS:
                errs.append(f'{where}: card type must be one of {sorted(CARDS)}')
            elif t == 'lesson' and (kind != 'lessons' or not isinstance(card.get('text'), str) or len(card['text'].split()) > 8):
                errs.append(f'{where}: a lesson card goes in the lessons chapter with "text" of at most 8 words')
            elif t == 'opening' and (not isinstance(card.get('ideas'), list) or not 1 <= len(card['ideas']) <= 3
                                     or any(len(str(i).split()) > 6 for i in card['ideas'])):
                errs.append(f'{where}: an opening card needs 1-3 "ideas" of at most 6 words')
            elif t == 'ideas' and (not isinstance(card.get('heading'), str) or not isinstance(card.get('points'), list)
                                   or not 1 <= len(card['points']) <= 3 or any(len(str(i).split()) > 8 for i in card['points'])):
                errs.append(f'{where}: an ideas card needs a "heading" and 1-3 "points" of at most 8 words')
            elif t == 'candidates' and (not isinstance(card.get('ply'), int) or not 1 <= card['ply'] <= n):
                errs.append(f'{where}: a candidates card needs the game "ply" it is about')
        for e in x.get('effects', []) or []:
            errs += _effect_errs(e, say, where)
        if kind == 'lessons' and not (isinstance(card, dict) and card.get('type') == 'lesson'):
            errs.append(f'{where}: every lessons line has a "lesson" card')
    if expected != n + 1:
        errs.append(f'the game chapters play plies up to {expected - 1}, but the game has {n}; play every ply')
    for k in sorted((key_plies or set()) & skipped):
        errs.append(f'ply {k} is a key moment; play it with "moves", not in a skip')
    for k in sorted((key_plies or set()) - played):
        if expected == n + 1:
            errs.append(f'ply {k} is a key moment and must be played')
    if thinks > MAX_THINKS:
        errs.append(f'{thinks} "think" pauses; use at most {MAX_THINKS}')
    if check_length:
        w = word_count(script)
        if not WORDS[0] <= w <= WORDS[1]:
            errs.append(f'the script is {w} words; it must be {WORDS[0]}-{WORDS[1]} words (5-9 minutes)')
    return errs


def _effect_errs(e: dict, say: str, where: str) -> list[str]:
    errs = []
    t = e.get('type')
    if t not in ('arrow', 'badge', 'ring', 'zoom', 'evalbar', 'slam', 'highlight', 'motif'):
        return [f'{where}: unknown effect type {t!r}']
    if not e.get('word') or not has_word(say, str(e['word'])):
        errs.append(f'{where}: effect word {e.get("word")!r} is not in the line')
    if t == 'arrow':
        if not (SQ.match(str(e.get('from'))) and SQ.match(str(e.get('to')))):
            errs.append(f'{where}: arrow needs from/to squares')
        if e.get('color') not in COLORS:
            errs.append(f'{where}: arrow color must be one of {sorted(COLORS)}')
    if t in ('badge', 'ring', 'zoom', 'motif') and not SQ.match(str(e.get('square'))):
        errs.append(f'{where}: {t} needs a square')
    if t == 'badge' and e.get('text') not in BADGES:
        errs.append(f'{where}: badge text must be one of {sorted(BADGES)}')
    if t == 'highlight' and (not isinstance(e.get('squares'), list) or not all(SQ.match(str(s)) for s in e['squares'])):
        errs.append(f'{where}: highlight needs "squares"')
    if t == 'motif':
        if str(e.get('name', '')).upper() not in MOTIFS:
            errs.append(f'{where}: motif name must be one of {sorted(MOTIFS)}')
        if not all(SQ.match(str(s)) for s in e.get('targets', []) or []):
            errs.append(f'{where}: motif targets must be squares')
    return errs
