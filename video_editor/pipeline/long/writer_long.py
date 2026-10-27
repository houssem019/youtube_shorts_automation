"""Claude writes the long video's script from the engine facts; code checks it.

1. outline: the story, the chapters, which moments get variations and pauses, the lessons, title and thumbnail
2. script: the full narration in the long-video format (schema_long), validated and retried with the errors
3. every "what if" line is played out and scored by Stockfish; a fact-check pass gets those results
4. fit: if the voiced video runs outside 5-10 minutes, Claude cuts or adds (never by talking faster)
Uses the Anthropic API if ANTHROPIC_API_KEY is set, else the Claude Code CLI, like the Shorts writer.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

import chess.engine

from ..writer_claude import _parse, facts as move_table
from .deep import check_line
from .schema_long import WORDS, __doc__ as SCHEMA_DOC, lines, validate, word_count

TARGET = (330, 540)   # seconds the finished video should run (5:30-9:00; YouTube long form, 5-10 min asked)
API_MODEL = 'claude-opus-5-5'

VOICE = """You write the narration for a long-form YouTube video (5-10 minutes, 16:9) that breaks down one chess
game. A narrator voice reads it while an animated board plays the moves next to a side panel. There are no
subtitles: everything you write is heard, so write for the ear.

Audience: club players who want to improve (roughly 1000-1800 rated). They should enjoy the story AND learn:
the ideas behind the moves, the opening's plans, the tactics, and the missed chances that would have won or saved
the game. Explain WHY, in plain words. Name tactics (fork, pin, skewer, overloaded piece) only when the facts
show them. Talk about plans (where pieces belong, which pawn break, which weakness to hit), not just moves.

Voice:
- A friendly, sharp coach who loves a good story. Natural spoken English, contractions, varied sentence length.
  Real reactions are fine ("And here it goes wrong."), but no hype and no shouting.
- Refer to the players as White and Black (never "I", "me", "my", or usernames).
- Say moves the way the "say" column spells them ("knight takes e5", "queen h4, check"), squares as "e5".
  You may also describe moves in words ("the bishop drops back"). No algebraic notation in "say" (no "Nxe5").
- Evals: say them rarely and in words ("White is clearly better", "about a pawn up", "completely winning").
- Avoid AI-sounding writing: no "Let's dive in", "Here's the thing", "buckle up", "game-changer", "masterclass",
  "insane", "absolutely", "crucial", "delve", "in conclusion", "a testament to", "journey"; no lists of three
  adjectives; no repeated "X? Y." patterns; no puns or punchlines; no emojis or hashtags; never begin two lines in a
  row the same way.
- Facts: use only what the facts below support (moves, engine evals, engine lines, tactics found by the
  detectors, clocks, opening book). Never invent a threat, line, eval or tactic. For general opening ideas you may
  use well-known, standard plans of the named opening, said in general terms.

Structure and pacing:
- cold_open (about 20 seconds, 35-60 words): lines with "show" on the most interesting position. Open a question
  the video answers; don't give away the answer or the result of the key moment. The title sequence plays after.
- game chapters (3-6, with short specific titles of at most 28 characters, like "Out of the book", "The knight
  on d5", "Eleven seconds"; the lessons chapter needs a title too):
  together they play every game ply from 1 to the end, in order. Move fast through quiet stretches ("spread" for
  a few natural moves, "skip" to fast-forward longer runs with a short bridging line), and slow right down on the
  moments that matter. The opening chapter explains the opening (one "opening" card) and says where the game left
  the book. The key moments get: the position explained, a "candidates" card or a "think" pause, the move
  played, and what should have happened shown as a variation. Show 4-8 variations in the video, each 2-6 moves,
  taken from the engine lines in the facts (shorten them freely; don't invent lines). After a variation the next
  game move automatically shows "BACK TO THE GAME".
- think: up to 3 "think" lines in the video; each ends by asking the viewer to pause and find the move
  ("Pause the video and find it."). A 5-second timer follows; reveal the answer in the very next line. A
  "candidates" card on a think line appears only after the timer, so it doesn't give the answer away.
- "show" is only for the cold open, lessons and outro. In game chapters, a line with none of moves / spread /
  skip / variation simply talks over the position on screen.
- The finish: for checkmate, a line for the mating move then a short "Checkmate." line with a slam effect; for
  resignation or time, a line saying so with a slam effect ("RESIGNS" / "TIME!").
- lessons (title like "What to take away"): 2-4 lines, each with a "lesson" card (max 8 words) and "show" on the
  position it comes from. Practical lessons a club player can use in their next game.
- outro: 1-2 short lines with "show" "final": a question that invites a comment. No begging for subscribes.
- A "stats" or "graph" card once near the end of the game chapters or in the lessons is good.

Length: {lo}-{hi} words in total (about 6-8 minutes). The voiced video is measured and you will be asked to
fix it if it's off.

Effects: use them to make the board easy to follow, about one line in two: arrows for plans, threats and better
moves (green = good move, red = threat, orange = a line of attack or a plan), badges ("??" after a blunder is
played, "!" for a strong move), highlight for key squares or a weak pawn chain, motif for a tactic the facts name
(name in capitals, square = the attacking piece, targets = what it hits), ring to point at a piece, zoom when the
action is in one corner. Every effect "word" and move "word" must be a word that appears in that line's "say".

Title: at most 70 characters, about THIS game's story, the way a good human chess YouTuber titles a breakdown.
True to the facts, sentence case, plain words, no emojis, hashtags, quotes, usernames, ALL CAPS or hype words
("insane", "shocking", "unbelievable", "genius", "masterclass", "destroyed"). Don't give away a puzzle answer.
thumb: 2-4 punchy words for the thumbnail and the cold open (e.g. "ONE MOVE TOO GREEDY"), true to the game.
summary: 1-3 plain sentences for the video description.
"""

OUTLINE = """First, plan the video. Read the facts and decide the story. Return ONLY this JSON:
{"title": str, "thumb": str, "summary": str,
 "chapters": [{"kind": "cold_open"|"game"|"lessons"|"outro", "title": str, "plies": [first, last] (game chapters only),
               "beats": [short notes: what this chapter says, which moments get a think pause, candidates card,
                         or variation (with the engine line you'll use), which tactics to name]}],
 "lessons": [str]}"""

SCRIPT = """Now write the full script for this outline (you may improve it). Return ONLY the JSON script."""

REVIEW = """You are fact-checking the narration of a chess video against the engine facts. Go through every
sentence. A sentence is wrong if it describes a move, capture, check, threat, tactic, plan, piece location, eval
or engine line that the facts don't support, or gets which side did what wrong. Also check every variation
against "Variation check" below: the engine scored each line after it is played; if a line is said to win
something but the check says otherwise (or the reverse), fix the words or the line. Common traps: "takes" when
it only attacks; the wrong square; calling a good move a mistake; a tactic name the detectors didn't find.
Check "title", "thumb" and "summary" the same way.
Fix every wrong sentence with the smallest change that makes it true (or delete the claim). Keep the tone,
structure, plies and effects; keep every "word" anchor present in its line; keep every rule of the format.
Return ONLY the full corrected JSON script."""

FIT = """The script below was voiced and the video runs {secs:.0f} seconds ({words} words). It must run
{lo}-{hi} seconds. {action}
{how}
Keep the tone, the title, the key moments, the variations that matter, the format rules and the facts.
Every "word" anchor must stay in its line. Return ONLY the full corrected JSON script."""


# ---------- calling Claude ----------

def _call_api(prompt: str) -> str:
    import anthropic  # optional dependency
    client = anthropic.Anthropic()
    msg = client.messages.create(model=API_MODEL, max_tokens=16000, messages=[{'role': 'user', 'content': prompt}])
    return ''.join(b.text for b in msg.content if getattr(b, 'type', '') == 'text')


def _call_cli(prompt: str) -> str:
    exe = shutil.which('claude') or shutil.which('claude.cmd')
    r = subprocess.run([exe, '-p', '--output-format', 'text'], input=prompt, capture_output=True, text=True,
                       encoding='utf-8', timeout=1500, cwd=tempfile.gettempdir())
    if r.returncode != 0:
        raise RuntimeError(f'claude CLI failed: {r.stderr[-500:]}')
    return r.stdout


def caller():
    if os.environ.get('ANTHROPIC_API_KEY'):
        return _call_api, 'Anthropic API'
    if shutil.which('claude') or shutil.which('claude.cmd'):
        return _call_cli, 'Claude Code CLI'
    return None, None


# ---------- facts ----------

def facts(a: dict, s: dict, ctx: dict) -> str:
    """Everything the writer may say, as text. ctx: opening, deep, stats, phases, style."""
    out = [move_table(a, s, ctx.get('style'))]
    op = ctx.get('opening')
    if op:
        out.append(f"\nOpening book (Lichess opening names): {op['name']} ({op['eco']}). The last named book position is "
                   f"after ply {op['bookPly']} ({op['line']}); {op['leftBy']}'s next move leaves the named lines.")
    else:
        out.append(f"\nOpening: {a.get('opening') or 'unknown'} (no named book line matched past the first moves).")
    st = ctx['stats']
    for c, name in (('w', 'White'), ('b', 'Black')):
        x = st['sides'][c]
        clock = (f"; lowest clock {x['lowestClock']} s" if x['lowestClock'] is not None else '') + \
                (f", under a minute from move {x['underAMinuteFromMove']}" if x['underAMinuteFromMove'] else '')
        out.append(f"{name}: accuracy {x['accuracy']}%, {x['blunders']} blunders, {x['mistakes']} mistakes, "
                   f"{x['inaccuracies']} inaccuracies{clock}.")
    ph = ctx.get('phases') or {}
    if ph.get('endgameStarts'):
        out.append(f"The endgame (queens off or little material left) starts around ply {ph['endgameStarts']}.")
    tc = a.get('timeControl') or ''
    if tc:
        base, _, inc = tc.partition('+')
        if base.isdigit():
            out.append(f"Time control: {int(base) // 60} minutes{f' + {inc} s per move' if inc else ''}.")
    out.append('\nKey moments, looked at deeper (depth 18, top 3 moves before the move was played):')
    for k, d in sorted(ctx['deep'].items()):
        p = a['plies'][k - 1]
        mv = f"{p['num']}{'.' if p['color'] == 'w' else '...'} {p['san']}"
        out.append(f"- ply {k} ({mv}, {'White' if p['color'] == 'w' else 'Black'}, {p['cls']}):")
        for i, c in enumerate(d['candidates'], 1):
            out.append(f"    candidate {i}: {c['say']} ({c['san']}), eval {c['ev']}, line {c['line']}")
        if d.get('playedMotifs'):
            out.append(f"    the move played: {'; '.join(d['playedMotifs'])}")
        if d.get('hanging'):
            out.append(f"    after the move played: {'; '.join(d['hanging'])}")
        if d.get('refutation'):
            r = d['refutation']
            extra = '; '.join(d.get('refutationMotifs') or [])
            out.append(f"    best reply to it: {r['say']} ({r['san']}), eval {r['ev']}, line {r['line']}"
                       + (f"; tactics: {extra}" if extra else '') + (f"; {d['refutationSwing']}" if d.get('refutationSwing') else ''))
        if d.get('bestMotifs') or d.get('bestSwing'):
            out.append(f"    the engine's move instead: {'; '.join(d.get('bestMotifs') or [])}"
                       + (f"; {d['bestSwing']}" if d.get('bestSwing') else ''))
    return '\n'.join(out)


def style_text(style: dict | None, recent_titles: list[str]) -> str:
    p = ''
    if style:
        p += f"\nTHIS VIDEO'S ANGLE: \"{style['name']}\".\n{style['brief']}\n"
    if recent_titles:
        p += ("\nTitles of the channel's latest long videos. Use a different wording and sentence pattern:\n- "
              + '\n- '.join(recent_titles) + '\n')
    return p


EXAMPLE = """Example of the format (a different game; match the format, not the words):
{"title": "He grabbed the pawn and walked into a pin", "thumb": "ONE PAWN TOO MANY",
 "summary": "A Caro-Kann where one greedy capture costs a piece. We look at the plans, the pin, and the move that held.",
 "chapters": [
  {"kind": "cold_open", "lines": [
    {"say": "Black is a pawn up here, and has exactly one move that keeps the game alive.", "show": 23,
     "effects": [{"type": "ring", "square": "f6", "word": "one"}]},
    {"say": "Most players at this level miss it. Let's see how we got here.", "show": 23}]},
  {"kind": "game", "title": "A quiet Caro-Kann", "lines": [
    {"say": "The game opens with e4 and c6, the Caro-Kann.", "moves": [{"ply": 1, "word": "e4"}, {"ply": 2, "word": "c6"}],
     "card": {"type": "opening", "ideas": ["Solid pawn on d5", "Develop the light bishop early", "Strike back with c5 later"]}},
    {"say": "Both sides develop normally for the next few moves.", "spread": [3, 8]},
    ...
    {"say": "Now Black has a choice. What would you play here? Pause the video and find it.", "think": true,
     "card": {"type": "candidates", "ply": 24}},
    {"say": "The answer is bishop e7, breaking the pin. If queen g3, Black simply castles.",
     "variation": {"from": 24, "san": ["Be7", "Qg3", "O-O"], "words": ["bishop", "queen", "castles"]}},
    {"say": "In the game Black took on b2 instead.", "moves": [{"ply": 24, "word": "took"}],
     "effects": [{"type": "badge", "square": "b2", "text": "?", "word": "took"}]},
    {"say": "And the next twelve moves change nothing, White just collects the pawns.", "skip": [25, 48]},
    ...]},
  {"kind": "lessons", "title": "What to take away", "lines": [
    {"say": "First, before grabbing a pawn, check what your queen leaves behind.", "show": 24,
     "card": {"type": "lesson", "text": "Check what your queen leaves behind"}}]},
  {"kind": "outro", "lines": [{"say": "Would you have found bishop e7? Tell me in the comments.", "show": "final"}]}]}
(The "..." stand for more lines; a real script has none.)"""


def _prompt(a, s, ctx, extra: str) -> str:
    lo, hi = WORDS
    return (VOICE.replace('{lo}', str(lo)).replace('{hi}', str(hi)) + style_text(ctx.get('style'), ctx.get('recent_titles', []))
            + f"\nScript format:\n{SCHEMA_DOC}\n{EXAMPLE}\n\nFacts for THIS game:\n{facts(a, s, ctx)}\n\n"
            + key_text(a, s) + extra)


def key_plies(a: dict, s: dict) -> set[int]:
    keys = {len(a['plies'])}
    if s.get('decisivePly'):
        keys.add(s['decisivePly'])
    if s.get('puzzle'):
        keys.add(s['puzzle']['ply'])
    return keys


def key_text(a: dict, s: dict) -> str:
    return (f"Key plies that must be played with \"moves\" (not skipped): {sorted(key_plies(a, s))}. "
            f"The game has {len(a['plies'])} plies.\n")


# ---------- checking variations with the engine ----------

def variation_report(script: dict, a: dict, stockfish: str) -> str:
    """One line per variation: where it starts, the moves, the eval after each move, tactics, material swing."""
    out = []
    eng = chess.engine.SimpleEngine.popen_uci(stockfish)
    try:
        prev_end = None
        for ci, li, _, x in lines(script):
            v = x.get('variation')
            if not v:
                continue
            fen = prev_end if v.get('continue') else a['plies'][v['from'] - 1]['fenBefore']
            if not fen:
                continue
            r = check_line(eng, fen, v['san'])
            if not r['ok']:
                out.append(f"- chapters[{ci}].lines[{li}]: {r['error']}")
                continue
            prev_end = r['fens'][-1]
            evs = ', '.join(f"{s_} ({c / 100:+.1f})" if m is None else f"{s_} (mate)" if m == 0 else f"{s_} (M{m})"
                            for s_, (c, m) in zip(v['san'], r['evals']))
            start = 'continuing the previous line' if v.get('continue') else f"instead of game ply {v['from']}"
            out.append(f"- chapters[{ci}].lines[{li}] ({start}): {evs}; ends {r['end']}"
                       + (f"; {r['swing']}" if r['swing'] else '') + (f"; tactics: {'; '.join(r['motifs'])}" if r['motifs'] else ''))
    finally:
        eng.quit()
    return '\n'.join(out) or '(no variations)'


# ---------- the passes ----------

def check(script: dict, a: dict, s: dict, length: bool = True) -> list[str]:
    errs = validate(script, a, key_plies(a, s), check_length=length)
    if not errs:
        cards = [x.get('card', {}).get('type') for _, _, _, x in lines(script) if x.get('card')]
        if cards.count('opening') != 1:
            errs.append(f'use exactly one "opening" card (in the first game chapter); there are {cards.count("opening")}')
        if 'candidates' not in cards:
            errs.append('use at least one "candidates" card at a key moment')
    return errs


def write(a: dict, s: dict, ctx: dict, stockfish: str, log=print, attempts: int = 4) -> dict | None:
    call, via = caller()
    if not call:
        log('Claude not available (no ANTHROPIC_API_KEY and no claude CLI); long videos need Claude.')
        return None
    log(f'Planning the video with {via}...')
    try:
        outline = _parse(call(_prompt(a, s, ctx, '\n' + OUTLINE)))
    except Exception as e:  # noqa: BLE001
        log(f'  outline failed ({e}); writing without one')
        outline = None
    base = '\n' + (f"Outline:\n{json.dumps(outline, indent=1)}\n\n" if outline else '') + SCRIPT
    errors, previous = None, None
    for i in range(attempts):
        extra = base
        if errors:
            extra += ("\n\nYour previous script had these problems; fix all of them and return the full corrected JSON:\n- "
                      + '\n- '.join(errors[:25]) + f"\n\nPrevious script:\n{previous}")
        try:
            log(f'Writing the script (attempt {i + 1})...')
            script = _parse(call(_prompt(a, s, ctx, extra)))
        except Exception as e:  # noqa: BLE001
            log(f'  Claude call failed: {e}')
            errors, previous = [f'Your reply could not be used: {e}. Return only valid JSON.'], None
            continue
        errors = check(script, a, s)
        if not errors:
            log(f'Script: {word_count(script)} words, {sum(1 for _ in lines(script))} lines.')
            return review(call, a, s, ctx, script, stockfish, log) or script
        log(f'  script had {len(errors)} problem(s): {errors[:3]}')
        previous = json.dumps(script)
    return None


def review(call, a, s, ctx, script, stockfish, log) -> dict | None:
    log('Checking the variations with Stockfish and fact-checking the script...')
    try:
        report = variation_report(script, a, stockfish)
        raw = call(f"{REVIEW}\n\nFacts:\n{facts(a, s, ctx)}\n\nVariation check (engine, after each move):\n{report}\n\n"
                   f"Script format:\n{SCHEMA_DOC}\n\nScript to check:\n{json.dumps(script, indent=1)}")
        fixed = _parse(raw)
    except Exception as e:  # noqa: BLE001
        log(f'  fact-check failed ({e}); keeping the first version')
        return None
    errs = check(fixed, a, s, length=False)
    if errs:
        log(f'  fact-checked script broke the format ({errs[:2]}); keeping the first version')
        return None
    return fixed


def fit(a: dict, s: dict, ctx: dict, script: dict, secs: float, stockfish: str, log=print) -> dict | None:
    call, _ = caller()
    if not call:
        return None
    lo, hi = TARGET
    words = word_count(script)
    goal = (lo + hi) / 2
    delta = max(30, round(abs(secs - goal) * words / max(secs, 1)))
    if secs > hi:
        action = f'Cut about {delta} words.'
        how = ('Ways to cut: turn quiet stretches into "skip" with a short bridging line, drop a less important '
               'variation, merge lines, shorten explanations that repeat, shorten the cold open and outro.')
    else:
        action = f'Add about {delta} words.'
        how = ('Ways to add: explain the plans and ideas at the key moments a little more, add a variation from the '
               'engine lines, describe what each side wants in the quieter phases (only what the facts support).')
    prompt = (FIT.format(secs=secs, words=words, lo=lo, hi=hi, action=action, how=how)
              + f"\n\nScript format:\n{SCHEMA_DOC}\n\nFacts:\n{facts(a, s, ctx)}\n\n{key_text(a, s)}\nScript:\n{json.dumps(script, indent=1)}")
    try:
        log(f'Fitting the video to {lo // 60}-{hi // 60} minutes: {action.lower()}')
        new = _parse(call(prompt))
    except Exception as e:  # noqa: BLE001
        log(f'  fitting failed ({e})')
        return None
    errs = check(new, a, s, length=False)
    if errs:
        log(f'  fitted script broke the format ({errs[:2]})')
        return None
    return review(call, a, s, ctx, new, stockfish, log) or new
