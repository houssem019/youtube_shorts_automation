"""Turn a commentary script into a voice track and a frame-accurate edit timeline for the Remotion video."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

from .script_schema import norm, start_ply
from .voice import SR, Narrator

FPS = 30
LEAD = 0.12


def _f(t: float) -> int:
    return int(round(t * FPS))


def build(a: dict, s: dict, script: dict, studio: Path, narrator: Narrator, voice_out: Path, log=print, look: dict | None = None) -> float:
    """look: from pipeline/styles.look_for (palette, opener, transition, zoom, headline); None = the original look."""
    plies, n = a['plies'], len(a['plies'])
    mate_end = bool(plies and plies[-1]['mate'])
    puzzle = s.get('puzzle')
    look = look or dict(opener='still', transition='tape', zoom=1.0, headline=None, colors=None)
    zoom = lambda peak: 1 + (peak - 1) * look['zoom']
    start = start_ply(script)  # the body starts here; the rewind goes back to the position before it

    # ---------- 1. voice every line ----------
    lines = [('hook', i, x) for i, x in enumerate(script['hook'])] + [('body', i, x) for i, x in enumerate(script['body'])] + \
            [('outro', i, x) for i, x in enumerate(script['outro'])]
    has_slam = any(e.get('type') == 'slam' for _, _, x in lines for e in x.get('effects', []) or [])
    clips, P, t = [], [], LEAD
    for k, (sec, i, x) in enumerate(lines):
        text = x['say'].strip()
        speed = 1.07 if x.get('spread') or x.get('skip') else (0.97 if text.endswith('?') or x.get('puzzle') else 1.05)
        if any(e.get('type') == 'slam' for e in x.get('effects', []) or []):
            speed = 0.92
        audio, words = narrator.say(text, speed=speed)
        pause = 0.15
        if x.get('puzzle'):
            pause = 3.3
        elif text.endswith('?') or any(e.get('type') == 'slam' for e in x.get('effects', []) or []):
            pause = 0.6 if sec != 'outro' else 0.4
        if k == len(lines) - 1:
            pause = 1.0
        P.append(dict(sec=sec, i=i, item=x, start=t + (words[0]['s'] if words else 0), end=t + (words[-1]['e'] if words else len(audio) / SR),
                      clip_start=t, words=[dict(t=w['t'], s=t + w['s'], e=t + w['e']) for w in words]))
        clips.append((t, audio))
        t += len(audio) / SR + pause
    total = t
    for k, p in enumerate(P):
        p['next'] = P[k + 1]['clip_start'] if k + 1 < len(P) else total

    track = np.zeros(int((total + 1) * SR), dtype=np.float32)
    for st, au in clips:
        i0 = int(st * SR)
        track[i0:i0 + len(au)] += au
    sf.write(str(voice_out), track, SR)

    def word_t(p, word):
        if word:
            for w in p['words']:
                if norm(w['t']) == norm(word):
                    return w['s']
        return p['start']

    def until(k, hold=0):
        return P[min(len(P) - 1, k + int(hold or 0))]['next']

    TL = dict(beats=[], statics=[], rewind=None, ffs=[], arrows=[], badges=[], cams=[], shakes=[], flashes=[], sfx=[], rings=[],
              slam=None, countdown=None, kingFall=None, evalPulse=[], evalSlow=[], captions=[], headline=None, look=look.get('colors'))
    sfx = lambda at, src, vol: TL['sfx'].append(dict(at=max(0, _f(at)), src=src, vol=vol))

    # ---------- 2. hook ----------
    hook = [p for p in P if p['sec'] == 'hook']
    shown = n  # the position on screen when the hook ends (the rewind starts from it)
    for k, p in enumerate(hook):
        show = p['item']['show']
        frm = 0 if k == 0 else p['clip_start']
        if show == 'rewind':
            from_ply = n if look['opener'] == 'still' else shown
            TL['rewind'] = dict(fromPly=from_ply, toPly=start - 1, label=f"BACK TO MOVE {plies[start - 1]['num']}",
                                style=look['transition'], **{'from': _f(frm), 'to': _f(p['end'])})
            if look['transition'] == 'tape':
                sfx(frm, 'tape', 0.45)
            else:
                sfx(frm, 'whoosh', 0.5)
                if look['transition'] == 'flash':
                    TL['flashes'].append(dict(at=_f(frm), color='#ffffff', strength=0.7))
        else:
            ply = n if show == 'final' else s['climaxPly']
            shown = ply
            sq = plies[ply - 1]['uci'][2:4]
            if k == 0 and look['opener'] == 'replay' and ply > 1:
                # the moves leading into the key moment play out, then the camera pushes in on the last one
                first = max(1, ply - 3)
                span = max(0.6, (p['next'] - frm) * 0.65)
                step = span / (ply - first + 1)
                t0 = frm + 0.25
                TL['statics'].append(dict(ply=first - 1, fallen=False, **{'from': _f(frm), 'to': _f(t0)}))
                for j, q in enumerate(range(first, ply + 1)):
                    TL['beats'].append(dict(ply=q, at=_f(t0 + step * j), dur=max(6, min(10, _f(step) - 2)), hook=True))
                land = t0 + step * (ply - first) + 0.33
                TL['cams'].append(dict(sq=sq, peak=zoom(1.16), **{'from': _f(land) - 4, 'to': _f(p['next'])}))
                sfx(0, 'riser', 0.35)
                sfx(land, 'boom', 0.55)
                continue
            if k == 0:
                # never open on a frozen board: the last moves into the key move play from frame 3 (move sounds + eval
                # swing) and the key move lands at about 1.1 s
                first = max(1, ply - 2)
                t0 = frm + 0.1
                TL['statics'].append(dict(ply=first - 1, fallen=False, **{'from': _f(frm), 'to': _f(t0)}))
                for j, q in enumerate(range(first, ply + 1)):
                    TL['beats'].append(dict(ply=q, at=_f(t0 + 0.35 * j), dur=9, hook=True))
                land = _f(t0 + 0.35 * (ply - first)) + 9
                TL['statics'].append(dict(ply=ply, fallen=mate_end and ply == n, **{'from': land, 'to': _f(p['next'])}))
                if look['opener'] != 'headline':  # the headline has its own boom
                    sfx(land / FPS, 'boom', 0.45)
                cam_from = land - 4
            else:
                TL['statics'].append(dict(ply=ply, fallen=mate_end and ply == n, **{'from': _f(frm), 'to': _f(p['next'])}))
                cam_from = _f(frm) - 8
            TL['cams'].append(dict(sq=sq, peak=zoom(1.16), **{'from': cam_from, 'to': _f(p['next'])}))
            if k == 0 and look['opener'] == 'headline' and look.get('headline'):
                TL['headline'] = dict(text=look['headline'], **{'from': 4, 'to': _f(p['next'])})
                sfx(0.13, 'boom', 0.6)
            elif k == 0:
                sfx(0, 'subdrop', 0.5)
            if show == 'final' and k > 0:
                at = next((w['s'] for w in p['words'] if 'mate' in norm(w['t']) or 'los' in norm(w['t']) or 'resign' in norm(w['t'])), frm)
                TL['flashes'].append(dict(at=_f(at), color='#ffffff', strength=0.55))
                TL['shakes'].append(dict(at=_f(at), amp=16))
                sfx(at, 'boom', 0.7)

    # ---------- 3. body: moves ----------
    body_idx = [k for k, p in enumerate(P) if p['sec'] == 'body']
    ply_line = {}
    for k in body_idx:
        p = P[k]
        x = p['item']
        if x.get('spread'):
            a0, z0 = x['spread']
            cnt = z0 - a0 + 1
            span = max(0.3, p['end'] - p['start'])
            step = span / cnt
            dur = max(4, min(9, _f(step) - 1))
            for j in range(cnt):
                TL['beats'].append(dict(ply=a0 + j, at=_f(p['start'] + step * j), dur=dur))
                ply_line[a0 + j] = k
        if x.get('skip'):
            # fast-forward: the run blurs past in at most 2 seconds, inside its own line
            a0, z0 = x['skip']
            cnt = z0 - a0 + 1
            span = min(2.0, max(0.6, p['end'] - p['start']))
            f0 = _f(p['start'])
            fr = max(1, _f(span))
            for j in range(cnt):
                at_j = f0 + (fr * j) // cnt
                nxt_j = f0 + (fr * (j + 1)) // cnt
                TL['beats'].append(dict(ply=a0 + j, at=at_j, dur=max(1, min(4, nxt_j - at_j)), ff=True))
            TL['ffs'].append(dict(fromPly=a0, toPly=z0, **{'from': f0 - 2, 'to': f0 + fr + 8}))
            sfx(p['start'] - 0.1, 'whoosh', 0.45)
            sfx(p['start'] + span, 'tick2', 0.3)
        for m in x.get('moves', []) or []:
            at = word_t(p, m['word'])
            last = m['ply'] == n and mate_end
            TL['beats'].append(dict(ply=m['ply'], at=_f(at) - 3, dur=16 if last else 10))
            ply_line[m['ply']] = k
            if last:
                sfx(at - 0.45, 'riser', 0.4)
                TL['cams'].append(dict(sq=plies[-1]['uci'][2:4], peak=zoom(1.28), **{'from': _f(at) - 4, 'to': _f(until(k, 1)) + 20}))
    body_beats = [b for b in TL['beats'] if not b.get('hook')]
    if TL['rewind'] and body_beats:
        # hold the position the rewind landed on until the first move of the body is played
        TL['statics'].append(dict(ply=start - 1, fallen=False, **{'from': TL['rewind']['to'], 'to': min(b['at'] for b in body_beats)}))
    TL['beats'].sort(key=lambda b: (b['at'], b['ply']))
    for b0, b1 in zip(TL['beats'], TL['beats'][1:]):  # never overlap two move animations (fast-forward frames may)
        if b1['at'] < b0['at'] + b0['dur'] and not (b0.get('ff') and b1.get('ff')):
            b1['at'] = b0['at'] + b0['dur']

    # ---------- 4. effects (body + outro) ----------
    badge_plies = set()
    for k, p in enumerate(P):
        if p['sec'] == 'hook':
            continue
        for e in p['item'].get('effects', []) or []:
            at = word_t(p, e.get('word'))
            typ = e['type']
            if typ == 'arrow':
                TL['arrows'].append(dict(a=e['from'], b=e['to'], color={'red': '#E5484D', 'green': '#30C77B', 'orange': '#F5A524'}[e['color']],
                                         dashed=e['color'] != 'green', **{'from': _f(at), 'to': _f(until(k, e.get('hold')))}))
                sfx(at, 'whoosh', 0.3)
            elif typ == 'badge':
                col = '#30C77B' if e['text'] in ('!', '!!') else ('#F5A524' if e['text'] in ('?', '?!') else '#E5484D')
                TL['badges'].append(dict(sq=e['square'], text=e['text'], color=col, **{'from': _f(at), 'to': _f(until(k, e.get('hold', 1)))}))
                if e['text'] in ('??', '?', '#'):
                    sfx(at, 'error', 0.5 if e['text'] == '??' else 0.35)
                if e['text'] == '??':
                    TL['flashes'].append(dict(at=_f(at), color='#E5484D', strength=0.28))
                    TL['shakes'].append(dict(at=_f(at), amp=8))
                for pl in plies:
                    if pl['uci'][2:4] == e['square']:
                        badge_plies.add(pl['ply'])
            elif typ == 'ring':
                TL['rings'].append(dict(sq=e['square'], color='#FFD43B', **{'from': _f(at), 'to': _f(until(k))}))
            elif typ == 'zoom':
                TL['cams'].append(dict(sq=e['square'], peak=zoom(1.14), **{'from': _f(at) - 4, 'to': _f(until(k, e.get('hold')))}))
            elif typ == 'evalbar':
                TL['evalPulse'].append(dict(**{'from': _f(at), 'to': _f(p['next'])}))
            elif typ == 'slam':
                _slam(TL, s, at, until(k), e.get('text'), sfx, mate_end)
        if p['sec'] == 'body' and re.search(r'\b(eval|engine)\b', p['item']['say'], re.I) and not any(_f(p['start']) <= ep['from'] < _f(p['next']) for ep in TL['evalPulse']):
            TL['evalPulse'].append(dict(**{'from': _f(p['start']), 'to': _f(p['next'])}))
        if p['item'].get('puzzle'):
            TL['countdown'] = dict(title=f"{puzzle['toMove'].upper()} TO MOVE" if puzzle else 'YOUR MOVE', sub='FIND THE BEST MOVE',
                                   **{'from': _f(p['end'] + 0.15), 'to': _f(p['end'] + 3.15)})
            for j in range(3):
                sfx(p['end'] + 0.15 + j, 'heartbeat', 0.75)
                sfx(p['end'] + 0.15 + j, 'tick2', 0.45)

    # ---------- 5. automatic polish the writer may have skipped ----------
    for pl in plies:
        if (pl['cls'] == 'blunder' or pl['ply'] == s.get('decisivePly')) and pl['ply'] not in badge_plies and pl['ply'] in ply_line and not pl['mate']:
            b = next(b for b in TL['beats'] if b['ply'] == pl['ply'] and not b.get('hook'))
            at = (b['at'] + b['dur'] + 8) / FPS
            k = ply_line[pl['ply']]
            TL['badges'].append(dict(sq=pl['uci'][2:4], text='??' if pl['cls'] == 'blunder' else '?', color='#E5484D' if pl['cls'] == 'blunder' else '#F5A524',
                                     **{'from': _f(at), 'to': _f(until(k, 1))}))
            sfx(at, 'error', 0.45)
        if pl['cls'] in ('blunder',) or pl['ply'] == s.get('decisivePly'):
            TL['evalSlow'].append(pl['ply'])
    if not has_slam and s['how'] in ('checkmate', 'resignation', 'time', 'abandonment'):
        last_body = body_idx[-1]
        p = P[last_body]
        at = next((w['s'] for w in p['words'] if norm(w['t']).startswith(('checkmate', 'mate', 'resign', 'time'))), p['end'])
        _slam(TL, s, at, until(last_body), None, sfx, mate_end)

    # board marks from earlier lines end when a fast-forward starts (the pieces under them fly past)
    for ff in TL['ffs']:
        for key in ('arrows', 'badges', 'rings', 'cams'):
            for e in TL[key]:
                if e['from'] < ff['from'] < e['to']:
                    e['to'] = ff['from']

    # ---------- 6. outro ----------
    for k, p in enumerate(P):
        if p['sec'] != 'outro':
            continue
        show = p['item']['show']
        if show == 'puzzle_answer' and puzzle:
            TL['statics'].append(dict(ply=puzzle['ply'] - 1, fallen=False, **{'from': _f(p['clip_start']), 'to': _f(p['next'])}))
            pz = plies[puzzle['ply'] - 1]
            if pz.get('bestUci'):
                f_, t_ = pz['bestUci'][:2], pz['bestUci'][2:4]
                at = word_t(p, t_) if any(norm(w['t']) == t_ for w in p['words']) else p['start'] + 0.3
                if not any(ar['b'] == t_ and ar['from'] >= _f(p['clip_start']) for ar in TL['arrows']):
                    TL['arrows'].append(dict(a=f_, b=t_, color='#30C77B', dashed=False, **{'from': _f(at), 'to': _f(p['next'])}))
                if not any(bd['sq'] == t_ and bd['from'] >= _f(p['clip_start']) for bd in TL['badges']):
                    TL['badges'].append(dict(sq=t_, text='!', color='#30C77B', **{'from': _f(at), 'to': _f(p['next'])}))
                sfx(at, 'whoosh', 0.35)
        else:
            TL['statics'].append(dict(ply=n, fallen=mate_end, **{'from': _f(p['clip_start']), 'to': _f(p['next']) + 30}))

    # ---------- 7. captions: 1-3 words, break at punctuation and pauses ----------
    for p in P:
        page = []

        def flush():
            if page:
                TL['captions'].append(dict(words=[dict(t=w['t'], f=_f(w['s'])) for w in page], **{'from': _f(page[0]['s']), 'to': _f(page[-1]['e'])}))
        for w in p['words']:
            if page and (len(page) >= 3 or w['s'] - page[-1]['e'] > 0.28):
                flush()
                page = []
            page.append(w)
            if re.search(r'[.,!?]$', w['t']):
                flush()
                page = []
        flush()
    C = TL['captions']
    for c0, c1 in zip(C, C[1:]):
        c0['to'] = min(c1['from'], c0['to'] + 15)
    if C:
        C[0]['from'] = 0
        C[-1]['to'] += 20

    # ---------- 8. who is who ----------
    uc = a.get('userColor')

    def label(c):
        pl = a['white'] if c == 'w' else a['black']
        if uc is None:
            name = 'WHITE' if c == 'w' else 'BLACK'
        else:
            name = pl['name'] if c == uc else 'OPPONENT'
        return dict(name=name, rating=pl['rating'], side=c)
    TL['meta'] = dict(orientation='b' if uc == 'b' else 'w', white=label('w'), black=label('b'),
                      badPlies=[p['ply'] for p in plies if p['cls'] == 'blunder'], lastPly=n,
                      fallenKing=('b' if plies[-1]['color'] == 'w' else 'w') if mate_end else None)
    TL['statics'].sort(key=lambda x: x['from'])
    TL['duration'] = _f(total) + 6

    game = dict(plies=[{k: p[k] for k in ('ply', 'num', 'color', 'san', 'moves', 'captured', 'capturedPiece', 'check', 'mate', 'cp', 'mateIn')} for p in plies],
                positions=a['positions'])
    (studio / 'src' / 'game.json').write_text(json.dumps(game))
    (studio / 'src' / 'timeline.json').write_text(json.dumps(TL))
    log(f'Timeline: {total:.1f} s, {len(TL["beats"])} moves, {len(C)} captions')
    return total


def _slam(TL, s, at, to, text, sfx, mate_end):
    title = text or {'checkmate': 'CHECKMATE', 'resignation': 'RESIGNS', 'time': 'TIME!', 'abandonment': 'GAME OVER'}.get(s['how'], 'GAME OVER')
    sub = f"IN {s['totalMoves']} MOVES" if s['how'] == 'checkmate' else ''
    TL['slam'] = dict(title=title.upper(), sub=sub, **{'from': _f(at), 'to': _f(to) + 10})
    TL['shakes'].append(dict(at=_f(at), amp=24))
    TL['flashes'].append(dict(at=_f(at), color='#ffffff', strength=0.65))
    sfx(at, 'slam', 0.8)
    sfx(at, 'boom', 0.8)
    sfx(at + 0.1, 'bell', 0.5)
    if mate_end:
        TL['kingFall'] = _f(at + 0.4)
