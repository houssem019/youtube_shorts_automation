"""Make a long (16:9, 5-10 minute) narrated breakdown of one game, plus its thumbnail.

    python make_long.py --pgn game.pgn --out long.mp4 --username houssem999 --stockfish C:\\path\\stockfish.exe

Steps: Stockfish analysis -> story -> opening book, deeper look at the key moments, tactics, stats ->
style -> Claude plans and writes the script -> variations checked by Stockfish -> fact-check -> voice ->
timeline (fit to 5-9 min) -> Remotion render (ChessLong) + thumbnail (ChessThumb) -> loudness mastering.
Writes <work>/upload.json (title, summary, chapters, opening, thumbnail) for the uploader.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pipeline import styles  # noqa: E402
from pipeline.analysis import analyse  # noqa: E402
from pipeline.long import briefs, deep, openings, writer_long  # noqa: E402
from pipeline.long.schema_long import validate  # noqa: E402
from pipeline.long.timeline_long import build  # noqa: E402
from pipeline.render import master_voice, render, still  # noqa: E402
from pipeline.story import find_story  # noqa: E402
from pipeline.voice import Narrator  # noqa: E402


def log(msg: str) -> None:
    print(f'[editor] {msg}', flush=True)


def ensure_short_stubs(studio: Path) -> None:
    """The Shorts composition is bundled too; give it placeholder data on a machine that never made a Short."""
    game, tl = studio / 'src' / 'game.json', studio / 'src' / 'timeline.json'
    if not game.exists():
        game.write_text(json.dumps(dict(plies=[], positions=[{}])))
    if not tl.exists():
        p = dict(name='', rating=None)
        tl.write_text(json.dumps(dict(duration=1, beats=[], statics=[], rewind=None, arrows=[], badges=[], cams=[], shakes=[],
                                      flashes=[], sfx=[], rings=[], slam=None, countdown=None, kingFall=None, evalPulse=[],
                                      evalSlow=[], captions=[], meta=dict(orientation='w', white=dict(p, side='w'),
                                                                          black=dict(p, side='b'), badPlies=[], lastPly=0, fallenKing=None))))


def thumb_info(a: dict, s: dict, script: dict) -> dict:
    """The thumbnail shows the cold open's key position (it goes with the thumbnail words). When a mistake led to
    it, that move gets a red arrow and the eval swing; otherwise it's the position before the decisive move."""
    def ev(p):
        return f"M{abs(p['mateIn'])}" if p['mateIn'] else f"{p['cp'] / 100:+.1f}"
    cold = script['chapters'][0]['lines'][0].get('show')
    k = len(a['plies']) if cold == 'final' else cold
    if isinstance(k, int) and k > 0 and a['plies'][k - 1]['cls'] in ('blunder', 'mistake'):
        p = a['plies'][k - 1]
        before = ev(a['plies'][k - 2]) if k > 1 else '+0.3'
        return dict(board=k, text=script['thumb'], arrow=[p['uci'][:2], p['uci'][2:4]],
                    swing=None if p['mate'] else f"{before} → {ev(p)}")
    k = s.get('decisivePly')
    if not k:
        return dict(board=len(a['plies']), text=script['thumb'], arrow=None, swing=None)
    p = a['plies'][k - 1]
    before = ev(a['plies'][k - 2]) if k > 1 else '+0.3'
    return dict(board=k - 1, text=script['thumb'], arrow=[p['uci'][:2], p['uci'][2:4]], swing=None if p['mate'] else f"{before} → {ev(p)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pgn', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--username', default=None)
    ap.add_argument('--stockfish', required=True)
    ap.add_argument('--voice', default='am_michael')
    ap.add_argument('--depth', type=int, default=16)
    ap.add_argument('--work', default=None, help='folder for the analysis, script, voice and thumbnail of this game')
    ap.add_argument('--no-render', action='store_true', help='stop after the timeline (preview: cd studio && npx remotion studio)')
    ap.add_argument('--thumb-only', action='store_true', help='with --script: only make the timeline and the thumbnail')
    ap.add_argument('--script', default=None, help='use an existing script (JSON) instead of writing one')
    ap.add_argument('--style', default=None, choices=list(styles.BY_ID), help='storytelling style (default: best fit)')
    ap.add_argument('--recent', default=None, help='JSON file with the styles/titles of the latest long videos (read only)')
    ap.add_argument('--resume', action='store_true', help='reuse <work>/script.json if it was written for this same game')
    args = ap.parse_args()

    t0 = time.time()
    pgn = Path(args.pgn).read_text(encoding='utf-8')
    work = Path(args.work) if args.work else Path(args.out).with_suffix('')
    work.mkdir(parents=True, exist_ok=True)
    studio = HERE / 'studio'
    ensure_short_stubs(studio)

    # analysis is reused when the same game was already analysed in this work folder (re-runs while editing)
    cache = work / 'analysis_long.json'
    same = (work / 'game.pgn').exists() and (work / 'game.pgn').read_text(encoding='utf-8') == pgn and cache.exists()
    (work / 'game.pgn').write_text(pgn, encoding='utf-8')
    if same and json.loads(cache.read_text())['depth'] == args.depth:
        log('Reusing the analysis of this game.')
        c = json.loads(cache.read_text())
        a, dd = c['a'], {int(k): v for k, v in c['deep'].items()}
    else:
        log('Analysing the game with Stockfish...')
        a = analyse(pgn, args.stockfish, args.username, depth=args.depth)
        dd = None
    s = find_story(a)
    if dd is None:
        dd = deep.deep_dive(a, s, args.stockfish, log=log)
        cache.write_text(json.dumps(dict(depth=args.depth, a=a, deep=dd)))
    ctx = dict(opening=openings.detect(pgn), deep=dd, stats=deep.stats(a), phases=deep.phases(a))
    (work / 'story.json').write_text(json.dumps(s, indent=1))
    op = ctx['opening']
    log(f"{s['winner'] or 'Nobody'} wins by {s['how']} in {s['totalMoves']} moves; turning point ply {s['decisivePly']}; "
        f"opening: {op['name'] if op else a.get('opening')}")

    recent = []
    if args.recent and Path(args.recent).exists():
        try:
            recent = json.loads(Path(args.recent).read_text(encoding='utf-8')).get('recent', [])
        except Exception as e:  # noqa: BLE001
            log(f'Could not read {args.recent} ({e}); choosing the style without history.')
    style, style_facts, why = styles.choose(a, s, [r.get('style') for r in recent], force=args.style)
    log(f"Style: {style['id']} ({style['name']}): {why}")
    ctx['style'] = dict(name=style['name'], brief=briefs.BRIEFS.get(style['id'], briefs.DEFAULT), facts=style_facts)
    ctx['recent_titles'] = [r['title'] for r in recent[-8:] if r.get('title')]

    if args.resume and same and (work / 'script.json').exists() and not args.script:
        args.script = str(work / 'script.json')
        log('Reusing the script written for this game in an earlier run.')
    if args.script:
        script = json.loads(Path(args.script).read_text(encoding='utf-8'))
        errs = validate(script, a, writer_long.key_plies(a, s), check_length=False)
        if errs:
            log(f'Given script is invalid: {errs[:3]}')
            return 2
    else:
        script = writer_long.write(a, s, ctx, args.stockfish, log=log)
        if not script:
            log('Claude could not write a valid script; no video was made.')
            return 3
    script['style'] = script.get('style') or style['id']
    (work / 'script.json').write_text(json.dumps(script, indent=1), encoding='utf-8')
    log(f"Title: {script['title']}")

    log('Recording the narrator...')
    narrator = Narrator(HERE / 'models', voice=args.voice, log=log)
    look = styles.look_for(style['id'], a, s)
    raw_voice = work / 'voice_raw.wav'
    secs, chapters = build(a, s, script, ctx, studio, narrator, raw_voice, args.stockfish, log=log, look=look)
    lo, hi = writer_long.TARGET
    for _ in range(2):  # a script that runs outside the target is cut or extended by Claude and voiced again
        if lo <= secs <= hi or args.script:
            break
        fitted = writer_long.fit(a, s, ctx, script, secs, args.stockfish, log=log)
        if not fitted:
            break
        fitted['style'] = script['style']
        script = fitted
        (work / 'script.json').write_text(json.dumps(script, indent=1), encoding='utf-8')
        secs, chapters = build(a, s, script, ctx, studio, narrator, raw_voice, args.stockfish, log=log, look=look)
    if not lo <= secs <= hi:
        log(f'Note: the video runs {secs / 60:.1f} min (target {lo / 60:.1f}-{hi / 60:.1f}).')

    # the thumbnail data goes into the same props file
    props_path = studio / 'public' / 'long' / 'props.json'
    props = json.loads(props_path.read_text(encoding='utf-8'))
    props['thumb'] = thumb_info(a, s, script)
    props_path.write_text(json.dumps(props), encoding='utf-8')
    master_voice(raw_voice, studio / 'public' / 'long' / 'voice.wav')

    meta = dict(title=script['title'], summary=script.get('summary'), chapters=chapters, style=script['style'],
                opening=(op or {}).get('name') or a.get('opening'), thumbnail=None, seconds=round(secs))
    if args.no_render and not args.thumb_only:
        (work / 'upload.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
        log('Timeline ready; skipping render. Preview with: cd studio && npx remotion studio (composition ChessLong)')
        return 0
    thumb = work / 'thumbnail.png'
    log('Making the thumbnail...')
    try:
        still(studio, 'ChessThumb', thumb)
        meta['thumbnail'] = str(thumb.resolve())
    except Exception as e:  # noqa: BLE001
        log(f'Thumbnail failed ({e}); the video is made without one.')
    (work / 'upload.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
    if args.thumb_only or args.no_render:
        log(f'Thumbnail: {thumb}')
        return 0
    render(studio, Path(args.out), log=log, composition='ChessLong', expect_s=props['duration'] / 30)
    log(f'Done in {(time.time() - t0) / 60:.0f} min: {args.out}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001  (so the reason shows up in app.log, not only in the console)
        log(f'Failed: {type(e).__name__}: {e}')
        raise
