"""Claude writes the commentary script from the engine facts, then it is validated.

Uses, in order: the Anthropic API (if ANTHROPIC_API_KEY is set), else the Claude Code CLI
(`claude -p`, uses your Claude plan). Returns None if neither works or the script stays invalid,
and the caller falls back to the built-in writer.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .script_schema import __doc__ as SCHEMA_DOC, validate, word_count

HERE = Path(__file__).parent
TARGET = (45, 50)  # seconds the finished video should run
MAX_WORDS = 125    # a first draft above this can't fit in TARGET

STYLE = """You write the voiceover for a chess YouTube Short about one game. A narrator voice reads it while an
animated board plays the moves, so every line must be speakable and in sync with the board.

Voice and style:
- Sound like a sharp, friendly human chess streamer talking over the game: contractions, short sentences,
  real reactions ("No no no.", "Wait.", "Oh, that's bad."). Energy rises toward the key moment.
- Explain the actual chess ideas when the facts support them: hanging pieces, pins, threats, why a move was a
  mistake, what the better move was. Use only what the facts below say. Never invent threats, lines or evals.
- Refer to the players as White and Black (never "I", "me", "my", or usernames).
- Say moves the way the "say" column spells them ("knight takes e5", "queen h4, check"). Squares as "e5".
- Avoid AI-sounding writing: no "Let's dive in", "Here's the thing", "game-changer", "masterclass", "insane",
  "absolutely", "brilliant" (unless the facts mark a brilliant move), no lists of three adjectives, no
  rhetorical "X? Y." patterns repeated, no punchline puns, no emojis, no hashtags, no calls to subscribe.
- One idea per video: build everything toward the turning point and the finish.

Length: the whole video must run 45-50 seconds. That is about 95-115 spoken words in total (hard maximum 125),
including the hook and outro. The voiced video is measured and you will be asked to fix it if it's off.
This is a highlight, not a replay: don't narrate the whole game. Viewers decide in the first two seconds and leave
during slow stretches, so spend the words on the moment that decides the game.

Structure:
- hook: half the viewers swipe away in the first two seconds, so the first line is short and pulls them in. The
  key move lands on the board in the first half-second (show "climax" or "final") and the first line talks over it:
  at most 9 words, aimed at the viewer, a challenge or an open question about this game. Don't give the ending away
  as a statement ("White walked past a forced mate" tells the whole story); keep it a question they stay to see
  answered. An optional second line (show "climax" or "final"), at most 8 words. Then the last line with show
  "rewind" plays while the board rewinds: 2-5 words that tell the viewer what to watch ("Watch the knight on f3.",
  "It starts with one pawn."). Never "Back to move eighteen": the screen already shows "BACK TO MOVE N".
  The whole hook including the rewind line: 16 words at most.
- body: pick where the story starts, usually 3-8 moves before the first key moment. The first body line plays that
  ply; the rewind goes straight back to the position before it and the screen shows "BACK TO MOVE N". Earlier
  moves are not shown; if the viewer needs context, say it in a few words ("Twenty moves in, it's dead level.").
  From the start ply, every ply to the last is played exactly once, in order:
  - key moves get their own words with "moves" anchored to the word where the piece should land;
  - 2-6 quiet plies can share one short line with "spread";
  - longer quiet stretches use "skip": the moves fast-forward in under 2 seconds with a "MOVE N" counter while a
    short bridging line is spoken ("Ten moves later, White is still pressing."). Use skip freely between key
    moments and before a long ending. Never skip the turning point, the puzzle move or the last move.
  Slow down only around the turning point and the finish.
- If a puzzle is given: right before that ply is played, add a line with "puzzle": true that ends with an
  invitation to pause ("Pause and find it."); the video then holds a 3-second countdown (counts toward the
  45-50 seconds). Do NOT reveal the answer before the outro.
- End the body with the finish: for checkmate, a line for the mating move then a separate "Checkmate." line with
  a slam effect; for resignation or time, a line saying so with a slam effect ("RESIGNS" / "TIME!").
- outro: if there was a puzzle, first reveal the answer in one short line with show "puzzle_answer" (you may add
  effects there), then one short closing line with show "final" (a question that invites a comment). Otherwise
  just the closing line. Keep the closing line under 12 words; the video loops back to the hook. Ask something
  answered with a move, a choice or a number, not yes/no: two real options from the facts ("Knight f6 or king g2:
  which do you play?"), the moment it went wrong, how fast they spotted it.

Title: the video's YouTube title, at most 40 characters, about THIS game's story (the turning point, the
mistake, how it ended), the way a human chess YouTuber would title it. It must be true to the facts. Sentence
case, plain words, no emojis, no hashtags, no quotes, no usernames, no ALL CAPS, no clickbait or hype words
("insane", "shocking", "unbelievable", "you won't believe", "genius", "masterclass", "destroyed"). Don't give
away the puzzle answer. The hashtags are added after it automatically.

Effects: use a few (not every line). Arrows for threats and better moves (green = good move, red = threat,
orange = a line of attack), badge "??" / "?" on the square of a bad move after it is played, "!" for the
answer, ring to point at a piece, zoom on the square where the action is, evalbar when you mention the eval.
Every effect and move "word" must be a word that appears in that line's "say".

Return ONLY the JSON object, no prose, no markdown fences."""


def facts(a: dict, s: dict, style: dict | None = None) -> str:
    lines = ['ply | move | side | SAN | say | eval after (White +, Black -) | quality | engine best instead']
    for p in a['plies']:
        ev = ('mate' if p['mate'] else (f"M{p['mateIn']}" if p['mateIn'] else f"{p['cp'] / 100:+.1f}"))
        best = '' if p['cls'] == 'best' or not p['bestSay'] else f"{p['bestSay']} ({p['bestLine']})"
        q = p['cls'] + (' (missed a forced mate)' if p.get('missedMate') else '')
        lines.append(f"{p['ply']} | {p['num']}{'.' if p['color'] == 'w' else '...'} | {'White' if p['color'] == 'w' else 'Black'} | {p['san']} | {p['say']} | {ev} | {q} | {best}")
    names = f"White: {a['white']['name']} ({a['white']['rating']}), Black: {a['black']['name']} ({a['black']['rating']})"
    story = json.dumps({k: v for k, v in s.items() if k != 'captures'}, indent=1)
    extra = ''
    if style and style.get('facts'):
        extra = '\nMore facts (checked from the engine and the game clocks):\n- ' + '\n- '.join(style['facts']) + '\n'
    return f"Game: {names}. Opening: {a['opening'] or 'unknown'}. Result: {a['result']} ({s['how']}).\nStory summary from the engine:\n{story}\n{extra}\nMoves:\n" + '\n'.join(lines)


def style_directions(style: dict | None) -> str:
    if not style:
        return ''
    p = (f"\nTHIS VIDEO'S STYLE: \"{style['name']}\". Every video on the channel uses a different storytelling style so "
         f"they don't feel the same. Where these directions differ from the hook/pacing/outro/title guidance above, "
         f"follow these; all format rules still apply.\n{style['brief']}\n")
    if style.get('recent_titles'):
        p += ("\nTitles of the channel's latest videos. Write a title with a different wording and sentence pattern "
              "(don't start it the same way as any of these):\n- " + '\n- '.join(style['recent_titles']) + '\n')
    return p


def build_prompt(a: dict, s: dict, errors: list[str] | None = None, previous: str | None = None, style: dict | None = None) -> str:
    example = (HERE / 'example_script.json').read_text()
    what = 'match this tone and density, not its content or its hook' if style else 'match this tone and density, not its content'
    p = (f"{STYLE}\n{style_directions(style)}\nScript format:\n{SCHEMA_DOC}\n\nExample script for a different game ({what}):\n{example}\n\n"
         f"Facts for THIS game:\n{facts(a, s, style)}\n")
    if s.get('puzzle'):
        p += f"\nPuzzle: put the puzzle line right before ply {s['puzzle']['ply']} is played. The answer is {s['puzzle']['answerSay']} (engine line {s['puzzle']['line']}).\n"
    if errors:
        p += "\nYour previous script had these problems, fix all of them and return the full corrected JSON:\n- " + '\n- '.join(errors) + f"\n\nPrevious script:\n{previous}\n"
    return p


def _call_api(prompt: str, model: str) -> str:
    import anthropic  # optional dependency
    client = anthropic.Anthropic()
    msg = client.messages.create(model=model, max_tokens=8000, messages=[{'role': 'user', 'content': prompt}])
    return ''.join(b.text for b in msg.content if getattr(b, 'type', '') == 'text')


def _call_cli(prompt: str, model: str | None) -> str:
    exe = shutil.which('claude') or shutil.which('claude.cmd')
    if not exe:
        raise RuntimeError('claude CLI not found')
    cmd = [exe, '-p', '--output-format', 'text']
    if model:
        cmd += ['--model', model]
    import tempfile
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding='utf-8', timeout=600, cwd=tempfile.gettempdir())
    if r.returncode != 0:
        raise RuntimeError(f'claude CLI failed: {r.stderr[-500:]}')
    return r.stdout


def _parse(text: str) -> dict:
    """The first complete JSON object in the reply (ignores fences and any note Claude adds after it)."""
    text = text.strip()
    start = text.find('{')
    if start < 0:
        raise ValueError('no JSON object in reply')
    obj, _ = json.JSONDecoder().raw_decode(text, start)
    return obj


REVIEW = """You are fact-checking a chess commentary script against the engine's move table.
Go through every sentence. A sentence is wrong if it describes a move, capture, check, threat, pin, piece
location, eval number or better move that the move table does not support, or gets which side did what wrong.
Common traps: saying a piece "takes" something when it only attacks or covers it; naming the wrong square;
calling a move a mistake when the table says it was good or best; inventing an engine line.
Check the "title" the same way (it must be true, at most 40 characters, and must not give away a puzzle answer).
Fix every wrong sentence with the smallest change that makes it true (or delete the claim). Keep the tone,
structure, plies and effects; if you change words, keep every "word" anchor present in its line.
Return ONLY the full corrected JSON script."""


def key_plies(a: dict, s: dict) -> set[int]:
    """Plies the body must play with "moves": the turning point, the puzzle move and the last move."""
    keys = {len(a['plies'])}
    if s.get('decisivePly'):
        keys.add(s['decisivePly'])
    if s.get('puzzle'):
        keys.add(s['puzzle']['ply'])
    return keys


def check(script: dict, a: dict, s: dict) -> list[str]:
    """Format errors, plus a word budget so a first draft can fit in TARGET seconds."""
    errs = validate(script, len(a['plies']), s['puzzle']['ply'] if s.get('puzzle') else None, require_title=True,
                    key_plies=key_plies(a, s))
    if not errs and word_count(script) > MAX_WORDS:
        errs.append(f'the script is {word_count(script)} words; the video must run 45-50 seconds, so keep it under {MAX_WORDS} '
                    '(start the body later, use "skip" for quiet stretches, shorten lines)')
    return errs


def review(call, a, s, script, n, puzzle_ply, log, style=None):
    try:
        log('Fact-checking the commentary...')
        raw = call(f"{REVIEW}\n\nMove table and story:\n{facts(a, s, style)}\n\nScript format:\n{SCHEMA_DOC}\n\nScript to check:\n{json.dumps(script, indent=1)}")
        fixed = _parse(raw)
    except Exception as e:  # noqa: BLE001
        log(f'  fact-check failed ({e}); keeping the first version')
        return None
    errs = validate(fixed, n, puzzle_ply, require_title=True, key_plies=key_plies(a, s))
    if errs:
        log(f'  fact-checked script broke the format ({errs[:2]}); keeping the first version')
        return None
    return fixed


def _caller(api_model: str, cli_model: str | None):
    """(call, how) for the Anthropic API if ANTHROPIC_API_KEY is set, else the Claude Code CLI; (None, None) if neither."""
    if os.environ.get('ANTHROPIC_API_KEY'):
        return (lambda p: _call_api(p, api_model)), 'Anthropic API'
    if shutil.which('claude') or shutil.which('claude.cmd'):
        return (lambda p: _call_cli(p, cli_model)), 'Claude Code CLI'
    return None, None


def write(a: dict, s: dict, log=print, api_model: str = 'claude-sonnet-5-5', cli_model: str | None = None, attempts: int = 3,
          style: dict | None = None) -> dict | None:
    """style: {"name", "brief", "facts", "recent_titles"} from pipeline/styles.py, or None for the plain prompt."""
    call, via = _caller(api_model, cli_model)
    if not call:
        log('Claude not available (no ANTHROPIC_API_KEY and no claude CLI); using the built-in writer.')
        return None
    n = len(a['plies'])
    puzzle_ply = s['puzzle']['ply'] if s.get('puzzle') else None
    errors, previous = None, None
    for i in range(attempts):
        try:
            log(f'Writing commentary with {via} (attempt {i + 1})...')
            raw = call(build_prompt(a, s, errors, previous, style))
            script = _parse(raw)
        except Exception as e:  # noqa: BLE001
            log(f'  Claude call failed: {e}')
            errors, previous = [f'Your reply could not be used: {e}. Return only valid JSON.'], None
            continue
        errors = check(script, a, s)
        if not errors:
            reviewed = review(call, a, s, script, n, puzzle_ply, log, style)
            return reviewed or script
        log(f'  script had {len(errors)} problem(s): {errors[:3]}')
        previous = json.dumps(script)
    return None


FIT = """The commentary script below was voiced and the video runs {secs:.1f} seconds ({words} words). It must run
{lo}-{hi} seconds. {action}
{how}
Keep everything else as it is: the tone, the title, the turning point, the puzzle line (if any), the finish and
the format rules. Don't add any claim the move table doesn't support. Every "word" anchor must stay in its line.
Return ONLY the full corrected JSON script."""


def fit(a: dict, s: dict, script: dict, secs: float, log=print, api_model: str = 'claude-sonnet-5-5', cli_model: str | None = None,
        style: dict | None = None) -> dict | None:
    """Ask Claude to shorten or lengthen a voiced script to TARGET seconds; None if it can't (keep the current one)."""
    call, _ = _caller(api_model, cli_model)
    if not call:
        return None
    lo, hi = TARGET
    words = word_count(script)
    delta = max(4, round(abs(secs - (lo + hi) / 2) * words / max(secs, 1)))
    if secs > hi:
        action = f'Cut about {delta} words.'
        how = ('Ways to cut: start the body later (the rewind then goes back less far), turn quiet stretches that are not '
               'key moments into one "skip" with a short line, merge or shorten lines, shorten the hook and the outro.')
    else:
        action = f'Add about {delta} words.'
        how = ('Ways to add: explain the idea behind the key move a little more (only what the move table supports), '
               'or start the body a few moves earlier.')
    prompt = (FIT.format(secs=secs, words=words, lo=lo, hi=hi, action=action, how=how) +
              f"\n\nScript format:\n{SCHEMA_DOC}\n\nFacts for this game:\n{facts(a, s, style)}\n")
    if s.get('puzzle'):
        prompt += f"\nPuzzle: the puzzle line goes right before ply {s['puzzle']['ply']} is played.\n"
    prompt += f"\nScript:\n{json.dumps(script, indent=1)}"
    try:
        log(f'Fitting the video to {lo}-{hi} s: {action.lower()}')
        new = _parse(call(prompt))
    except Exception as e:  # noqa: BLE001
        log(f'  fitting failed ({e})')
        return None
    errs = check(new, a, s)
    if errs:
        log(f'  fitted script broke the format ({errs[:2]})')
        return None
    puzzle_ply = s['puzzle']['ply'] if s.get('puzzle') else None
    return review(call, a, s, new, len(a['plies']), puzzle_ply, log, style) or new
