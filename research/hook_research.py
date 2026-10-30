"""Hook research: what do the chess Shorts that beat their channel's average do in the first seconds?

Standalone: nothing in main.py / video_editor uses it. Own venv (research/.venv: yt-dlp + faster-whisper),
system ffmpeg. Work files go to data/research/ (git-ignored). Downloads are for local analysis only; nothing from
other channels is ever reused in our videos.

Stages (each cached, re-run any time):
  channels  seed channels from YouTube's Shorts search, list each channel's recent Shorts with views
  select    keep chess Shorts that beat their channel's median views (outlier score), a few per channel
  fetch     full metadata (likes, comments, date, subscribers) + a <=480p download
  analyze   ffmpeg: first-3-seconds contact sheet, cuts and visual change per second, time to first sound;
            faster-whisper: word timestamps -> first spoken word, hook text, words per second, last line
  report    data/research/report.md + summary.json

  research\\.venv\\Scripts\\python research\\hook_research.py all [--own data\\temp\\edited.mp4]
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'research'
VID = OUT / 'videos'
SHEETS = OUT / 'sheets'

SEARCHES = ['chess', 'chess checkmate', 'chess blunder', 'chess game', 'chess puzzle', 'chess trap',
            'chess brilliant move', 'chess rapid', 'chess comeback', 'chess tactics']
SHORTS_FILTER = 'EgIQCQ%253D%253D'
CHESS_WORDS = re.compile(r'chess|checkmate|\bmate\b|gambit|queen|knight|bishop|rook|pawn|blunder|brilliant|'
                         r'magnus|hikaru|opening|trap|elo|\bgm\b|stalemate|castl|en passant|sacrific', re.I)
PER_CHANNEL_SHORTS = 60
MIN_VIEWS = 200_000
MIN_OUTLIER = 2.0
MAX_PER_CHANNEL = 3
N_SELECT = 40


def load(name, default=None):
    p = OUT / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')


def ydl(opts):
    import yt_dlp
    return yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'ignoreerrors': True, **opts})


# ---------- 1. channels ----------
def stage_channels():
    channels = {}
    with ydl({'extract_flat': True, 'playlistend': 80}) as y:
        for q in SEARCHES:
            url = f'https://www.youtube.com/results?search_query={q.replace(" ", "+")}&sp={SHORTS_FILTER}'
            info = y.extract_info(url, download=False) or {}
            for e in info.get('entries') or []:
                if e and e.get('channel_url') and CHESS_WORDS.search(e.get('title') or ''):
                    channels.setdefault(e['channel_url'], e.get('channel') or '')
            print(f'search "{q}": {len(channels)} channels so far')
    shorts = load('shorts.json', {})
    with ydl({'extract_flat': True, 'playlistend': PER_CHANNEL_SHORTS}) as y:
        for i, (url, name) in enumerate(channels.items()):
            if url in shorts:
                continue
            info = y.extract_info(url.rstrip('/') + '/shorts', download=False) or {}
            shorts[url] = dict(channel=name, items=[dict(id=e['id'], title=e.get('title') or '', views=e.get('view_count'))
                                                     for e in info.get('entries') or [] if e and e.get('id')])
            print(f'[{i + 1}/{len(channels)}] {name}: {len(shorts[url]["items"])} shorts')
            save('shorts.json', shorts)


# ---------- 2. select ----------
def stage_select():
    picked = []
    for url, ch in load('shorts.json', {}).items():
        items = [s for s in ch['items'] if s['views']]
        if len(items) < 8:
            continue  # too few Shorts to know what's normal for the channel
        median = statistics.median(s['views'] for s in items)
        best = sorted((s for s in items if CHESS_WORDS.search(s['title']) and s['views'] >= MIN_VIEWS
                       and s['views'] >= MIN_OUTLIER * median), key=lambda s: -s['views'] / median)
        for s in best[:MAX_PER_CHANNEL]:
            picked.append(dict(s, channel=ch['channel'], channel_url=url, channel_median=median,
                               outlier=round(s['views'] / median, 1)))
    # rank by outlier score, but a big view count also counts (log-ish blend)
    picked.sort(key=lambda s: -(min(s['outlier'], 30) * (s['views'] ** 0.25)))
    save('selected.json', picked[:N_SELECT])
    for s in picked[:N_SELECT]:
        print(f'{s["views"]:>11,}  x{s["outlier"]:<5} {s["channel"][:22]:<22} {s["title"][:60]}')


# ---------- 3. fetch ----------
def stage_fetch():
    VID.mkdir(parents=True, exist_ok=True)
    meta = load('meta.json', {})
    opts = {'format': 'b[height<=480][ext=mp4]/bv[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=720]/b',
            'outtmpl': str(VID / '%(id)s.%(ext)s'), 'merge_output_format': 'mp4'}
    with ydl(opts) as y:
        for s in load('selected.json', []):
            if s['id'] in meta and any(VID.glob(s['id'] + '.*')):
                continue
            info = y.extract_info('https://www.youtube.com/shorts/' + s['id'], download=True)
            if not info:
                print('failed:', s['id'])
                continue
            meta[s['id']] = dict(s, title=info.get('title'), duration=info.get('duration'), likes=info.get('like_count'),
                                 comments=info.get('comment_count'), views=info.get('view_count') or s['views'],
                                 upload_date=info.get('upload_date'), subscribers=info.get('channel_follower_count'),
                                 description=(info.get('description') or '')[:500], width=info.get('width'),
                                 height=info.get('height'))
            print(f'{s["id"]}: {meta[s["id"]]["duration"]}s  {meta[s["id"]]["title"][:60]}')
            save('meta.json', meta)


# ---------- 4. analyze ----------
def ffmpeg(*args):
    return subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *args], capture_output=True, text=True,
                          errors='replace').stderr


def visual(path):
    """Per-frame scene-change scores -> hard cuts and how much the picture changes in each second."""
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-an', '-vf',
                          "scale=320:-2,select='gte(scene,0)',metadata=print:file=-", '-f', 'null', '-'],
                         capture_output=True, text=True, errors='replace').stdout
    t, frames = None, []
    for line in out.splitlines():
        m = re.search(r'pts_time:([\d.]+)', line)
        if m:
            t = float(m.group(1))
        m = re.search(r'scene_score=([\d.]+)', line)
        if m and t is not None:
            frames.append((t, float(m.group(1))))
    cuts = [round(t, 2) for t, s in frames if s > 0.3 and t > 0.05]
    per_sec = {}
    for t, s in frames:
        per_sec.setdefault(int(t), []).append(s)
    change = [round(sum(v) * 100, 1) for _, v in sorted(per_sec.items())]  # summed change per second, x100
    return dict(cuts=cuts, change_per_sec=change)


def first_sound(path):
    err = ffmpeg('-i', str(path), '-vn', '-af', 'silencedetect=noise=-35dB:d=0.1', '-f', 'null', '-')
    starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', err)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', err)]
    if not starts or starts[0] > 0.05:
        return 0.0
    return round(ends[0], 2) if ends else None


def sheet(path, vid):
    SHEETS.mkdir(parents=True, exist_ok=True)
    png = SHEETS / f'{vid}.png'
    # frames at 0, 0.5, 1, 1.5, 2, 2.5 s side by side = what the viewer sees before deciding to swipe
    ffmpeg('-y', '-t', '3', '-i', str(path), '-vf', 'fps=2,scale=240:-2,tile=6x1', '-frames:v', '1', str(png))
    return png.name


_model = None


def transcribe(path):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel('small', device='cpu', compute_type='int8')
    import numpy as np
    # decode with ffmpeg ourselves: faster-whisper's own loader breaks on newer PyAV releases
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    segs, info = _model.transcribe(audio, word_timestamps=True, vad_filter=False, beam_size=5)
    words = [dict(w=w.word.strip(), s=round(w.start, 2), e=round(w.end, 2)) for seg in segs for w in seg.words or []]
    text = lambda ws: ' '.join(w['w'] for w in ws)
    first = words[0]['s'] if words else None
    speech = (words[-1]['e'] - words[0]['s']) if len(words) > 1 else 0
    return dict(language=info.language, n_words=len(words), first_word=first,
                words_first3s=sum(1 for w in words if w['s'] < 3),
                wps=round(len(words) / speech, 2) if speech > 0 else None,
                hook=text([w for w in words if w['s'] < 3.5]), last=text([w for w in words if w['s'] > words[-1]['e'] - 4]) if words else '',
                full=text(words), words=words)


def analyze_one(path, vid):
    return dict(visual(path), first_sound=first_sound(path), sheet=sheet(path, vid), speech=transcribe(path))


def stage_analyze(own):
    res = load('analysis.json', {})
    meta = load('meta.json', {})
    todo = [(vid, next(VID.glob(vid + '.*'), None)) for vid in meta]
    todo += [('OWN_' + Path(p).stem, Path(p)) for p in own]
    for vid, path in todo:
        if vid in res or not path or not path.exists():
            continue
        print('analyzing', vid)
        res[vid] = analyze_one(path, vid)
        save('analysis.json', res)


# ---------- 5. report ----------
def stage_report():
    meta, res = load('meta.json', {}), load('analysis.json', {})
    rows = []
    for vid, a in res.items():
        m = meta.get(vid, dict(title=vid, channel='OURS', views=None))
        sp, ch = a['speech'], a['change_per_sec']
        rows.append(dict(id=vid, own=vid.startswith('OWN_'), title=m.get('title'), channel=m.get('channel'),
                         views=m.get('views'), outlier=m.get('outlier'), duration=m.get('duration') or len(ch),
                         like_rate=round(100 * m['likes'] / m['views'], 2) if m.get('likes') and m.get('views') else None,
                         comment_rate=round(1000 * m['comments'] / m['views'], 2) if m.get('comments') and m.get('views') else None,
                         first_sound=a['first_sound'], first_word=sp['first_word'], words_first3s=sp['words_first3s'],
                         wps=sp['wps'], lang=sp['language'], cuts=len(a['cuts']),
                         first_cut=a['cuts'][0] if a['cuts'] else None,
                         change_0_3s=round(sum(ch[:3]) / max(1, len(ch[:3])), 1),
                         change_rest=round(sum(ch[3:]) / max(1, len(ch[3:])), 1),
                         hook=sp['hook'], last=sp['last'], sheet=a['sheet']))
    save('summary.json', rows)
    theirs = [r for r in rows if not r['own']]

    def med(k, rs=theirs):
        v = [r[k] for r in rs if isinstance(r[k], (int, float))]
        return round(statistics.median(v), 2) if v else None

    keys = ['duration', 'first_sound', 'first_word', 'words_first3s', 'wps', 'cuts', 'first_cut', 'change_0_3s',
            'change_rest', 'like_rate', 'comment_rate']
    L = ['# Chess Shorts hook research', '', f'{len(theirs)} outlier chess Shorts (views >= {MIN_VIEWS:,}, at least '
         f'{MIN_OUTLIER}x their channel median) vs our own.', '',
         '| metric | outliers (median) | ' + ' | '.join(r['id'] for r in rows if r['own']) + ' |',
         '|---|---|' + '---|' * sum(r['own'] for r in rows)]
    for k in keys:
        L.append(f'| {k} | {med(k)} | ' + ' | '.join(str(r[k]) for r in rows if r['own']) + ' |')
    L += ['', 'change = summed ffmpeg scene score per second x100 (how much the picture moves); cuts = hard cuts '
          '(score > 0.3); like_rate = % of views; comment_rate = comments per 1000 views.', '',
          '## Videos', '']
    for r in sorted(rows, key=lambda r: (not r['own'], -(r['views'] or 0))):
        L += [f'### {r["title"]}', f'{r["channel"]} - {r["views"] and f"{r["views"]:,}"} views, x{r["outlier"]} channel median, '
              f'{r["duration"]}s, lang {r["lang"]}, likes {r["like_rate"]}%, comments {r["comment_rate"]}/1k',
              f'- first sound {r["first_sound"]}s, first word {r["first_word"]}s, {r["words_first3s"]} words in 3 s, '
              f'{r["wps"]} words/s, {r["cuts"]} cuts (first at {r["first_cut"]}s), change 0-3 s {r["change_0_3s"]} vs '
              f'rest {r["change_rest"]}', f'- hook: "{r["hook"]}"', f'- ending: "{r["last"]}"',
              f'- ![](sheets/{r["sheet"]})', '']
    (OUT / 'report.md').write_text('\n'.join(L), encoding='utf-8')
    print('\n'.join(L[:len(keys) + 8]))
    print('->', OUT / 'report.md')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['channels', 'select', 'fetch', 'analyze', 'report', 'all'])
    ap.add_argument('--own', nargs='*', default=[], help='our own Short files to compare (e.g. data/temp/edited.mp4)')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    stages = ['channels', 'select', 'fetch', 'analyze', 'report'] if a.stage == 'all' else [a.stage]
    for s in stages:
        print(f'== {s} ==')
        stage_analyze(a.own) if s == 'analyze' else globals()['stage_' + s]()


if __name__ == '__main__':
    sys.exit(main())
