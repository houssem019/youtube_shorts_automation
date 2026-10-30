"""The commentary script format, shared by every writer, and its validator.

A script is JSON:
{
  "title": str,                                                            # YouTube title, max 40 characters
  "hook": [{"say": str, "show": "climax" | "final" | "rewind"}],          # 1-3 lines; the key move plays in under the first
  "body":  [{"say": str,
             "moves":  [{"ply": int, "word": str}],      # a move lands when that word is spoken
             "spread": [first_ply, last_ply],            # or: play a run of quiet moves across the line
             "skip":   [first_ply, last_ply],            # or: fast-forward a run of moves in 1-2 seconds
             "puzzle": bool,                             # pause for viewers after this line
             "effects": [Effect]}],
  "outro": [{"say": str, "show": "final" | "puzzle_answer", "effects": [Effect]}]
}
Effect = {"type": "arrow", "from": sq, "to": sq, "color": "red|green|orange", "word": str, "hold": int}
       | {"type": "badge", "square": sq, "text": "??|?|!|!!|#", "word": str, "hold": int}
       | {"type": "ring",  "square": sq, "word": str}
       | {"type": "zoom",  "square": sq, "word": str, "hold": int}
       | {"type": "evalbar", "word": str}
       | {"type": "slam", "text": str, "word": str}
The body starts at any ply (the rewind goes straight back to the position before it); from there every ply
to the last must be played exactly once, in order. Key plies (turning point, puzzle, last move) can't be skipped.
"""
from __future__ import annotations

import re

SQ = re.compile(r'^[a-h][1-8]$')
COLORS = {'red', 'green', 'orange'}
BADGES = {'??', '?', '!', '!!', '#', '?!'}
TITLE_MAX = 40  # the uploader appends 32 characters of hashtags; YouTube allows 100


def norm(w: str) -> str:
    return re.sub(r"[^\w'\-]", '', w).lower().strip("'")


def has_word(say: str, word: str) -> bool:
    return norm(word) in [norm(w) for w in say.split()]


def ply_range(item: dict) -> tuple[int, int] | None:
    """(first, last) ply a body line plays, or None."""
    for k in ('spread', 'skip'):
        if item.get(k):
            return item[k][0], item[k][1]
    ms = [m.get('ply') for m in item.get('moves', []) or [] if isinstance(m.get('ply'), int)]
    return (ms[0], ms[-1]) if ms else None


def start_ply(script: dict) -> int:
    """The first ply the body plays (1 = the whole game is shown)."""
    for b in script.get('body', []):
        r = ply_range(b)
        if r:
            return r[0]
    return 1


def word_count(script: dict) -> int:
    return sum(len(x.get('say', '').split()) for sec in ('hook', 'body', 'outro') for x in script.get(sec, []))


def validate(script: dict, n_plies: int, has_puzzle_ply: int | None = None, require_title: bool = False,
             key_plies: set[int] | None = None) -> list[str]:
    """key_plies: plies that must be played normally (not skipped, not before the start)."""
    errs: list[str] = []
    if not isinstance(script, dict):
        return ['script is not an object']
    title = script.get('title')
    if title is not None or require_title:
        if not isinstance(title, str) or not title.strip():
            errs.append('"title" must be a non-empty string')
        elif len(title.strip()) > TITLE_MAX:
            errs.append(f'"title" is {len(title.strip())} characters, max {TITLE_MAX}')
        elif re.search(r'[#<>]', title):
            errs.append('"title" must not contain #, < or >')
    for sec in ('hook', 'body', 'outro'):
        if not isinstance(script.get(sec), list) or not script[sec]:
            errs.append(f'"{sec}" must be a non-empty list')
    if errs:
        return errs

    def check_effects(item, where):
        for e in item.get('effects', []) or []:
            t = e.get('type')
            if t not in ('arrow', 'badge', 'ring', 'zoom', 'evalbar', 'slam'):
                errs.append(f'{where}: unknown effect type {t!r}')
                continue
            if not e.get('word') or not has_word(item['say'], e['word']):
                errs.append(f'{where}: effect word {e.get("word")!r} is not in the line')
            if t == 'arrow':
                if not (SQ.match(str(e.get('from'))) and SQ.match(str(e.get('to')))):
                    errs.append(f'{where}: arrow needs from/to squares')
                if e.get('color') not in COLORS:
                    errs.append(f'{where}: arrow color must be one of {sorted(COLORS)}')
            if t in ('badge', 'ring', 'zoom') and not SQ.match(str(e.get('square'))):
                errs.append(f'{where}: {t} needs a square')
            if t == 'badge' and e.get('text') not in BADGES:
                errs.append(f'{where}: badge text must be one of {sorted(BADGES)}')

    for i, h in enumerate(script['hook']):
        if not h.get('say'):
            errs.append(f'hook[{i}] has no "say"')
        if h.get('show') not in ('climax', 'final', 'rewind'):
            errs.append(f'hook[{i}].show must be climax, final or rewind')
    if script['hook'] and script['hook'][-1].get('show') != 'rewind':
        errs.append('the last hook line must have show="rewind" (it plays while the board rewinds)')

    start = start_ply(script)
    if not 1 <= start <= n_plies:
        errs.append(f'the body starts at ply {start}, but the game has plies 1-{n_plies}')
        return errs
    for k in sorted(key_plies or ()):
        if k < start:
            errs.append(f'ply {k} is a key moment, but the body starts at ply {start}; start before it')
    expected = start
    skipped: set[int] = set()
    for i, b in enumerate(script['body']):
        where = f'body[{i}]'
        say = b.get('say', '')
        if not say:
            errs.append(f'{where} has no "say"')
            continue
        if len(say.split()) > 32:
            errs.append(f'{where} is too long ({len(say.split())} words, max 32)')
        if sum(bool(b.get(k)) for k in ('moves', 'spread', 'skip')) > 1:
            errs.append(f'{where}: use only one of "moves", "spread" or "skip"')
        for k in ('spread', 'skip'):
            if b.get(k):
                rng = b[k]
                if not (isinstance(rng, list) and len(rng) == 2 and all(isinstance(v, int) for v in rng)):
                    errs.append(f'{where}: {k} must be [first_ply, last_ply]')
                    continue
                a, z = rng
                if a != expected or z < a:
                    errs.append(f'{where}: {k} {rng} should start at ply {expected}')
                if k == 'skip':
                    skipped |= set(range(a, z + 1))
                expected = max(expected, z + 1)
        for m in b.get('moves', []) or []:
            if m.get('ply') != expected:
                errs.append(f'{where}: move ply {m.get("ply")} out of order, expected {expected}')
            if not has_word(say, m.get('word', '')):
                errs.append(f'{where}: move word {m.get("word")!r} is not in the line')
            expected = max(expected, (m.get('ply') or 0) + 1)
        if b.get('puzzle') and has_puzzle_ply and expected != has_puzzle_ply:
            errs.append(f'{where}: the puzzle line must come right before ply {has_puzzle_ply} is played (next ply here is {expected})')
        check_effects(b, where)
    if expected != n_plies + 1:
        errs.append(f'the body plays plies up to {expected - 1}, but the game has {n_plies}')
    for k in sorted((key_plies or set()) & skipped):
        errs.append(f'ply {k} is a key moment; play it with "moves", not in a skip')

    for i, o in enumerate(script['outro']):
        if not o.get('say'):
            errs.append(f'outro[{i}] has no "say"')
        if o.get('show') not in ('final', 'puzzle_answer'):
            errs.append(f'outro[{i}].show must be final or puzzle_answer')
        check_effects(o, f'outro[{i}]')

    words = word_count(script)
    if words > 420:
        errs.append(f'script is {words} words; keep it under 420 so the Short stays under 3 minutes')
    return errs
