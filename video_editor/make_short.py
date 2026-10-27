"""Make an edited, commentated chess Short from one PGN.

    python make_short.py --pgn game.pgn --out edited.mp4 --username houssem999 --stockfish C:\\path\\stockfish.exe

Steps: Stockfish analysis -> find the story -> write commentary (Claude, else built-in) -> fact-check ->
voice -> word-timed edit timeline -> Remotion render -> loudness mastering.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pipeline import styles, writer_claude, writer_template  # noqa: E402
from pipeline.analysis import analyse  # noqa: E402
from pipeline.render import master_voice, render  # noqa: E402
from pipeline.script_schema import validate  # noqa: E402
from pipeline.story import find_story  # noqa: E402
from pipeline.timeline import build  # noqa: E402
from pipeline.voice import Narrator  # noqa: E402


def log(msg: str) -> None:
    print(f'[editor] {msg}', flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pgn', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--username', default=None)
    ap.add_argument('--stockfish', required=True)
    ap.add_argument('--voice', default='af_heart')
    ap.add_argument('--writer', default='auto', choices=['auto', 'claude', 'template'])
    ap.add_argument('--depth', type=int, default=16)
    ap.add_argument('--work', default=None, help='folder for the analysis, script and voice of this game')
    ap.add_argument('--no-render', action='store_true', help='stop after building the timeline (for previewing in Remotion Studio)')
    ap.add_argument('--script', default=None, help='use an existing commentary script (JSON) instead of writing one')
    ap.add_argument('--style', default=None, choices=list(styles.BY_ID), help='storytelling style (default: best fit for the game)')
    ap.add_argument('--recent', default=None, help='JSON file with the styles/titles of the latest uploads (read only)')
    args = ap.parse_args()

    t0 = time.time()
    pgn = Path(args.pgn).read_text(encoding='utf-8')
    work = Path(args.work) if args.work else Path(args.out).with_suffix('')
    work.mkdir(parents=True, exist_ok=True)
    (work / 'game.pgn').write_text(pgn, encoding='utf-8')

    log('Analysing the game with Stockfish...')
    a = analyse(pgn, args.stockfish, args.username, depth=args.depth)
    s = find_story(a)
    (work / 'analysis.json').write_text(json.dumps(a))
    (work / 'story.json').write_text(json.dumps(s, indent=1))
    log(f"{s['winner'] or 'Nobody'} wins by {s['how']} in {s['totalMoves']} moves; turning point ply {s['decisivePly']}; puzzle: {bool(s['puzzle'])}")

    puzzle_ply = s['puzzle']['ply'] if s.get('puzzle') else None
    script = None
    claude_style = None  # set when Claude wrote the script (then it can also fit it to the target length)
    if args.script:
        script = json.loads(Path(args.script).read_text(encoding='utf-8'))
        errs = validate(script, len(a['plies']), puzzle_ply)
        if errs:
            log(f'Given script is invalid: {errs[:3]}')
            return 2
    if script is None and args.writer in ('auto', 'claude'):
        recent = []
        if args.recent and Path(args.recent).exists():
            try:
                recent = json.loads(Path(args.recent).read_text(encoding='utf-8')).get('recent', [])
            except Exception as e:  # noqa: BLE001
                log(f'Could not read {args.recent} ({e}); choosing the style without history.')
        style, style_facts, why = styles.choose(a, s, [r.get('style') for r in recent], force=args.style)
        log(f"Style: {style['id']} ({style['name']}): {why}")
        style_info = dict(name=style['name'], brief=style['brief'], facts=style_facts,
                          recent_titles=[r['title'] for r in recent[-8:] if r.get('title')])
        script = writer_claude.write(a, s, log=log, style=style_info)
        if script:
            script['style'] = style['id']
            claude_style = style_info
            log('Commentary written by Claude.')
    if script is None:
        if args.writer == 'claude':
            log('Claude could not write a valid script.')
            return 3
        log('Using the built-in commentary writer.')
        script = writer_template.write(a, s, seed=hash(pgn) & 0xFFFF)
        script['style'] = 'template'
    (work / 'script.json').write_text(json.dumps(script, indent=1), encoding='utf-8')
    log(f"Title: {script.get('title') or '(none)'}")

    log('Recording the narrator...')
    narrator = Narrator(HERE / 'models', voice=args.voice, log=log)
    studio = HERE / 'studio'
    raw_voice = work / 'voice_raw.wav'
    look = styles.look_for(script.get('style'), a, s)
    log(f"Look: {look['palette']} colours, {look['opener']} opening, {look['transition']} transition"
        + (f", headline \"{look['headline']}\"" if look['headline'] else ''))
    secs = build(a, s, script, studio, narrator, raw_voice, log=log, look=look)
    lo, hi = writer_claude.TARGET
    for _ in range(2):  # a Claude script that runs outside 45-50 s is shortened/lengthened and voiced again
        if lo <= secs <= hi + 0.5 or claude_style is None:
            break
        fitted = writer_claude.fit(a, s, script, secs, log=log, style=claude_style)
        if not fitted:
            break
        fitted['style'] = script['style']
        script = fitted
        (work / 'script.json').write_text(json.dumps(script, indent=1), encoding='utf-8')
        secs = build(a, s, script, studio, narrator, raw_voice, log=log, look=look)
    if not lo <= secs <= hi + 0.5:
        log(f'Note: the video runs {secs:.1f} s (target {lo}-{hi} s).')
    master_voice(raw_voice, studio / 'public' / 'voice.wav')

    if args.no_render:
        log('Timeline ready; skipping render. Preview with: cd studio && npx remotion studio')
        return 0
    render(studio, Path(args.out), log=log)
    log(f'Done in {time.time() - t0:.0f} s: {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
