"""Turn a long-video script into a voice track and a frame-accurate edit for the ChessLong composition.

The board is driven by a list of board states (`boards`: every game position, then every variation position)
and `events` (set a board, or animate a move into a board), so "what if" lines animate like game moves.
Output: studio/public/long/props.json and the raw voice track. No captions (long videos have none).
"""
from __future__ import annotations

import json
from pathlib import Path

import chess
import chess.engine
import numpy as np
import soundfile as sf

from ..voice import SR, Narrator
from .deep import candidates, check_line
from .schema_long import lines as script_lines, norm

FPS = 30
LEAD = 0.3
TITLE_SEQ = 3.6      # seconds of the title sequence after the cold open
CHAPTER_CARD = 1.7   # seconds of a chapter card (no voice)
THINK = 5.0          # seconds of a "pause and find it" timer
END_HOLD = 10.0      # seconds of end screen after the last word (YouTube end-screen elements go here)
COLORS = {'red': '#E5484D', 'green': '#30C77B', 'orange': '#F5A524'}


def _f(t: float) -> int:
    return int(round(t * FPS))


def _pos(board: chess.Board) -> dict:
    return {chess.square_name(s): p.symbol() for s, p in board.piece_map().items()}


def _label(num: int, color: str, san: str) -> str:
    return f"{num}{'.' if color == 'w' else '...'} {san}"


def _anim(board: chess.Board, mv: chess.Move) -> tuple[list, str | None]:
    anim = [[chess.square_name(mv.from_square), chess.square_name(mv.to_square)]]
    if board.is_castling(mv):
        rook = {chess.G1: ('h1', 'f1'), chess.C1: ('a1', 'd1'), chess.G8: ('h8', 'f8'), chess.C8: ('a8', 'd8')}[mv.to_square]
        anim.append(list(rook))
    cap = None
    if board.is_capture(mv):
        sq = mv.to_square if not board.is_en_passant(mv) else mv.to_square + (-8 if board.turn else 8)
        cap = chess.square_name(sq)
    return anim, cap


def _speed(x: dict) -> float:
    say = x['say'].strip()
    if x.get('skip') or x.get('spread'):
        return 1.04
    if x.get('think') or any(e.get('type') == 'slam' for e in x.get('effects', []) or []):
        return 0.94
    return 0.98 if say.endswith('?') else 1.0


def build(a: dict, s: dict, script: dict, ctx: dict, studio: Path, narrator: Narrator, voice_out: Path,
          stockfish: str, log=print, look: dict | None = None) -> tuple[float, list[dict]]:
    """Returns (seconds, YouTube chapters [{t, title}])."""
    plies, n = a['plies'], len(a['plies'])
    mate_end = bool(plies and plies[-1]['mate'])
    chapters = script['chapters']

    # ---------- boards: the game positions ----------
    clocks = {'w': None, 'b': None}
    boards = [dict(pos=a['positions'][0], last=None, check=None, mate=False, cp=30, mateIn=None, label='Start', cls=None,
                   main=0, prev=None, anim=None, captured=None, clocks=dict(clocks))]
    for p in plies:
        if p.get('clock') is not None:
            clocks[p['color']] = round(p['clock'])
        boards.append(dict(pos=a['positions'][p['ply']], last=p['moves'][0], check=p['check'], mate=p['mate'], cp=p['cp'],
                           mateIn=p['mateIn'], label=_label(p['num'], p['color'], p['san']), cls=p['cls'], main=p['ply'],
                           prev=p['ply'] - 1, anim=p['moves'], captured=p['captured'], clocks=dict(clocks)))

    # ---------- variations: new boards, scored by the engine ----------
    eng = chess.engine.SimpleEngine.popen_uci(stockfish)
    var_boards: dict[tuple[int, int], list[int]] = {}
    cand_cards: dict[int, list[dict]] = {}
    try:
        prev_end = None  # (board index, fen) at the end of the last variation
        for ci, li, _, x in script_lines(script):
            v = x.get('variation')
            card = x.get('card') or {}
            if card.get('type') == 'candidates':
                k = card['ply']
                d = (ctx.get('deep') or {}).get(k)
                cand_cards[k] = d['candidates'] if d else candidates(eng, plies[k - 1]['fenBefore'], 18)
            if not v:
                continue
            if v.get('continue') and prev_end:
                base, fen = prev_end
            else:
                base, fen = v['from'] - 1, plies[v['from'] - 1]['fenBefore']
            r = check_line(eng, fen, v['san'])
            if not r['ok']:
                raise ValueError(f'variation at chapters[{ci}].lines[{li}]: {r["error"]}')
            board = chess.Board(fen)
            idx, prev = [], base
            base_clocks = boards[base]['clocks']
            for san, (cp, mate), nxt in zip(v['san'], r['evals'], r['fens']):
                mv = board.parse_san(san)
                anim, cap = _anim(board, mv)
                color = 'w' if board.turn else 'b'
                num = board.fullmove_number
                board.push(mv)
                king = chess.square_name(board.king(board.turn)) if board.is_check() else None
                boards.append(dict(pos=_pos(board), last=anim[0], check=king, mate=board.is_checkmate(), cp=cp, mateIn=mate,
                                   label=_label(num, color, san), cls=None, main=None, prev=prev, anim=anim, captured=cap,
                                   clocks=base_clocks))
                prev = len(boards) - 1
                idx.append(prev)
            var_boards[(ci, li)] = idx
            prev_end = (prev, board.fen())
    finally:
        eng.quit()

    # ---------- 1. voice every line, leaving room for the cards between ----------
    P, clips, t = [], [], LEAD
    title_seq = None
    chapter_cards = []
    was_var = False
    for ci, ch in enumerate(chapters):
        if ci == 1:
            title_seq = (t, t + TITLE_SEQ)
            t += TITLE_SEQ + 0.3
        if ch['kind'] in ('game', 'lessons'):
            chapter_cards.append(dict(ci=ci, start=t))
            t += CHAPTER_CARD + 0.25
        for li, x in enumerate(ch['lines']):
            if x.get('variation') and not x['variation'].get('continue') and not was_var:
                t += 0.45  # the board changes to the variation before the line starts
            was_var = bool(x.get('variation')) or (was_var and not any(x.get(k) for k in ('moves', 'spread', 'skip', 'show')))
            text = x['say'].strip()
            audio, words = narrator.say(text, speed=_speed(x))
            dur = len(audio) / SR
            P.append(dict(ci=ci, li=li, kind=ch['kind'], item=x, clip_start=t,
                          start=t + (words[0]['s'] if words else 0), end=t + (words[-1]['e'] if words else dur),
                          words=[dict(t=w['t'], s=t + w['s'], e=t + w['e']) for w in words]))
            clips.append((t, audio))
            pause = 0.42
            if text.endswith('?'):
                pause = 0.7
            if x.get('think'):
                pause = THINK + 0.6
            if any(e.get('type') == 'slam' for e in x.get('effects', []) or []):
                pause = 1.1
            if li == len(ch['lines']) - 1:
                pause = max(pause, 0.75)
            t += dur + pause
    voice_end = t
    total = t + END_HOLD
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
                if norm(w['t']) == norm(str(word)):
                    return w['s']
        return p['start']

    def until(k, hold=0):
        """End of line k (+hold lines), never past the end of its chapter."""
        j = k
        for _ in range(int(hold or 0)):
            if j + 1 < len(P) and P[j + 1]['ci'] == P[k]['ci']:
                j += 1
        return P[j]['next']

    TL = dict(events=[], arrows=[], badges=[], rings=[], highlights=[], motifs=[], cams=[], shakes=[], flashes=[], sfx=[],
              cards=[], thinks=[], variations=[], backs=[], chapterCards=[], chapterLabels=[], evalPulse=[], evalSlow=[],
              slam=None, kingFall=None, coldOpen=None, titleSeq=None, endScreen=None)
    sfx = lambda at, src, vol: TL['sfx'].append(dict(at=max(0, _f(at)), src=src, vol=vol))
    ev = TL['events']

    def set_board(at, b):
        ev.append(dict(at=_f(at), board=b, dur=0))

    def move_to(at_frame, b, dur, ff=False):
        ev.append(dict(at=at_frame, board=b, dur=dur, ff=ff))

    # ---------- 2. chapters, title sequence, cold open ----------
    for c in chapter_cards:
        ch = chapters[c['ci']]
        num = sum(1 for x in chapter_cards if x['ci'] <= c['ci'])
        TL['chapterCards'].append(dict(num=num, title=ch['title'], **{'from': _f(c['start']), 'to': _f(c['start'] + CHAPTER_CARD)}))
        sfx(c['start'], 'whoosh', 0.35)
    for ci, ch in enumerate(chapters):
        ps = [p for p in P if p['ci'] == ci]
        if ch['kind'] in ('game', 'lessons') and ps:
            TL['chapterLabels'].append(dict(title=ch['title'], **{'from': _f(ps[0]['clip_start']), 'to': _f(ps[-1]['next'])}))
    if title_seq:
        TL['titleSeq'] = dict(**{'from': _f(title_seq[0]), 'to': _f(title_seq[1])})
        sfx(title_seq[0], 'boom', 0.45)
    cold = [p for p in P if p['kind'] == 'cold_open']
    if cold:
        TL['coldOpen'] = dict(text=script['thumb'].upper(), **{'from': 0, 'to': _f(title_seq[0] if title_seq else cold[-1]['next'])})
        sfx(0, 'subdrop', 0.4)
    outro = [p for p in P if p['kind'] == 'outro']
    if outro:
        TL['endScreen'] = dict(**{'from': _f(outro[0]['clip_start']), 'to': _f(total) + 1})

    # ---------- 3. the board: game moves, variations, still positions ----------
    shown = 0
    in_var = None  # the open variation span
    ply_line: dict[int, int] = {}
    board_at_line: dict[int, int] = {}

    def close_var(at):
        nonlocal in_var
        if in_var:
            in_var['to'] = _f(at)
            TL['variations'].append(in_var)
            in_var = None

    def back_to_game(p, target):
        nonlocal shown
        if shown != target:
            close_var(p['clip_start'])
            set_board(p['clip_start'], target)
            TL['backs'].append(dict(**{'from': _f(p['clip_start']), 'to': _f(p['clip_start'] + 1.5)}))
            sfx(p['clip_start'], 'whoosh', 0.3)
            shown = target

    for k, p in enumerate(P):
        x = p['item']
        if p['kind'] in ('cold_open', 'lessons', 'outro'):
            close_var(p['clip_start'])
            b = n if x['show'] == 'final' else x['show']
            if b != shown or k == 0:
                set_board(p['clip_start'] if k else 0, b)
                shown = b
            if p['kind'] == 'cold_open' and b > 0:
                TL['cams'].append(dict(sq=plies[b - 1]['uci'][2:4], peak=1.12, **{'from': _f(p['clip_start']), 'to': _f(p['next'])}))
            board_at_line[k] = shown
            continue
        if x.get('moves') or x.get('spread') or x.get('skip'):
            first = x['moves'][0]['ply'] if x.get('moves') else (x.get('spread') or x.get('skip'))[0]
            back_to_game(p, first - 1)
        if x.get('spread'):
            a0, z0 = x['spread']
            cnt = z0 - a0 + 1
            step = max(0.3, p['end'] - p['start']) / cnt
            dur = max(5, min(12, _f(step) - 1))
            for j in range(cnt):
                move_to(_f(p['start'] + step * j), a0 + j, dur)
                ply_line[a0 + j] = k
            shown = z0
        if x.get('skip'):
            a0, z0 = x['skip']
            cnt = z0 - a0 + 1
            span = min(3.0, max(0.8, p['end'] - p['start']))
            f0, fr = _f(p['start']), max(1, _f(span))
            for j in range(cnt):
                at_j = f0 + (fr * j) // cnt
                move_to(at_j, a0 + j, max(1, min(4, f0 + (fr * (j + 1)) // cnt - at_j)), ff=True)
            TL['ffs'] = TL.get('ffs', []) + [dict(fromPly=a0, toPly=z0, **{'from': f0 - 2, 'to': f0 + fr + 8})]
            sfx(p['start'] - 0.1, 'whoosh', 0.35)
            shown = z0
        for m in x.get('moves', []) or []:
            at = word_t(p, m['word'])
            last = m['ply'] == n and mate_end
            move_to(_f(at) - 3, m['ply'], 18 if last else 12)
            ply_line[m['ply']] = k
            shown = m['ply']
            if last:
                sfx(at - 0.45, 'riser', 0.35)
                TL['cams'].append(dict(sq=plies[-1]['uci'][2:4], peak=1.18, **{'from': _f(at) - 4, 'to': _f(until(k, 1)) + 20}))
        v = x.get('variation')
        if v:
            idx = var_boards[(p['ci'], p['li'])]
            base = boards[idx[0]]['prev']
            if not v.get('continue') or in_var is None:
                close_var(p['clip_start'])
                frm = p['clip_start'] - 0.45
                set_board(frm, base)
                bp = plies[base] if base < n else None  # the game move this line replaces
                crumb = f"INSTEAD OF {_label(bp['num'], bp['color'], bp['san'])}" if bp else 'WHAT IF'
                in_var = dict(crumb=crumb, boards=[], **{'from': _f(frm)})
                sfx(frm, 'whoosh', 0.3)
            in_var['boards'] += idx
            ws = v.get('words')
            if ws:
                ats = [word_t(p, w) for w in ws]
            else:
                step = max(0.5, p['end'] - p['start']) / len(idx)
                ats = [p['start'] + step * j for j in range(len(idx))]
            last_at = -99
            for b, at in zip(idx, ats):
                fr = max(_f(at) - 3, last_at + 13)
                move_to(fr, b, 12)
                last_at = fr
            shown = idx[-1]
        board_at_line[k] = shown
    close_var(voice_end)
    ev.sort(key=lambda e: e['at'])
    for e0, e1 in zip(ev, ev[1:]):  # never overlap two move animations (fast-forward frames may)
        if e1['dur'] and e1['at'] < e0['at'] + e0['dur'] and not (e0.get('ff') and e1.get('ff')):
            e1['at'] = e0['at'] + e0['dur']

    # ---------- 4. effects, cards, think pauses ----------
    badge_plies = set()
    card_spans = []
    for k, p in enumerate(P):
        x = p['item']
        for e in x.get('effects', []) or []:
            at = word_t(p, e.get('word'))
            typ = e['type']
            if typ == 'arrow':
                TL['arrows'].append(dict(a=e['from'], b=e['to'], color=COLORS[e['color']], dashed=e['color'] != 'green',
                                         **{'from': _f(at), 'to': _f(until(k, e.get('hold')))}))
            elif typ == 'badge':
                col = '#30C77B' if e['text'] in ('!', '!!') else ('#F5A524' if e['text'] in ('?', '?!') else '#E5484D')
                TL['badges'].append(dict(sq=e['square'], text=e['text'], color=col, **{'from': _f(at), 'to': _f(until(k, e.get('hold', 1)))}))
                if e['text'] in ('??', '?'):
                    sfx(at, 'error', 0.4 if e['text'] == '??' else 0.28)
                if e['text'] == '??':
                    TL['flashes'].append(dict(at=_f(at), color='#E5484D', strength=0.18))
                    TL['shakes'].append(dict(at=_f(at), amp=5))
                for pl in plies:
                    if pl['uci'][2:4] == e['square'] and ply_line.get(pl['ply']) == k:
                        badge_plies.add(pl['ply'])
            elif typ == 'ring':
                TL['rings'].append(dict(sq=e['square'], color='#FFD43B', **{'from': _f(at), 'to': _f(until(k))}))
            elif typ == 'highlight':
                TL['highlights'].append(dict(squares=e['squares'], color=COLORS.get(e.get('color'), '#FFD43B'),
                                             **{'from': _f(at), 'to': _f(until(k, e.get('hold')))}))
            elif typ == 'motif':
                TL['motifs'].append(dict(name=str(e['name']).upper(), sq=e['square'], targets=e.get('targets') or [],
                                         **{'from': _f(at), 'to': _f(until(k, e.get('hold')))}))
                sfx(at, 'bong', 0.25)
            elif typ == 'zoom':
                TL['cams'].append(dict(sq=e['square'], peak=1.14, **{'from': _f(at) - 4, 'to': _f(until(k, e.get('hold')))}))
            elif typ == 'evalbar':
                TL['evalPulse'].append(dict(**{'from': _f(at), 'to': _f(p['next'])}))
            elif typ == 'slam':
                _slam(TL, s, at, until(k), e.get('text'), sfx, mate_end)
        card = x.get('card')
        if card:
            data = dict(type=card['type'])
            if card['type'] == 'opening':
                op = ctx.get('opening') or {}
                data.update(name=op.get('name') or a.get('opening') or 'Opening', eco=op.get('eco'), ideas=card['ideas'])
            elif card['type'] == 'ideas':
                data.update(heading=card['heading'], points=card['points'])
            elif card['type'] == 'candidates':
                pl = plies[card['ply'] - 1]
                data.update(title=f"{'WHITE' if pl['color'] == 'w' else 'BLACK'} TO MOVE", move=_label(pl['num'], pl['color'], '?'),
                            items=[dict(san=c['san'], ev=c['ev'], cp=c['cp'], mate=c['mate']) for c in cand_cards[card['ply']]],
                            played=pl['san'])
            elif card['type'] == 'lesson':
                data.update(num=sum(1 for q in P[:k + 1] if (q['item'].get('card') or {}).get('type') == 'lesson'), text=card['text'])
            elif card['type'] == 'stats':
                data.update(sides=ctx['stats']['sides'])
            # on a "find the move" line the engine's answers only appear once the timer is over
            start = p['end'] + 0.3 + THINK if x.get('think') and card['type'] == 'candidates' else p['clip_start']
            card_spans.append(dict(k=k, data=data, start=start))
        if x.get('think'):
            side = _side_to_move(boards, board_at_line.get(k, 0))
            t0 = p['end'] + 0.3
            TL['thinks'].append(dict(title='PAUSE THE VIDEO', sub=f'{side} TO MOVE', **{'from': _f(t0), 'to': _f(t0 + THINK)}))
            for j in range(int(THINK)):
                sfx(t0 + j, 'tick2', 0.3)
            sfx(t0 + THINK, 'bell', 0.3)
    for j, c in enumerate(card_spans):
        k = c['k']
        end = until(k, 3 if c['data']['type'] != 'lesson' else 0)
        if j + 1 < len(card_spans):
            end = min(end, P[card_spans[j + 1]['k']]['clip_start'])
        if end > c['start']:
            TL['cards'].append(dict(**c['data'], **{'from': _f(c['start']), 'to': _f(end)}))

    # ---------- 5. polish the writer may have skipped ----------
    for pl in plies:
        if (pl['cls'] == 'blunder' or pl['ply'] == s.get('decisivePly')) and pl['ply'] not in badge_plies and pl['ply'] in ply_line and not pl['mate']:
            e = next(e for e in ev if e['board'] == pl['ply'] and e['dur'] and not e.get('ff'))
            at = (e['at'] + e['dur'] + 8) / FPS
            TL['badges'].append(dict(sq=pl['uci'][2:4], text='??' if pl['cls'] == 'blunder' else '?',
                                     color='#E5484D' if pl['cls'] == 'blunder' else '#F5A524',
                                     **{'from': _f(at), 'to': _f(until(ply_line[pl['ply']], 1))}))
            sfx(at, 'error', 0.35)
        if pl['cls'] == 'blunder' or pl['ply'] == s.get('decisivePly'):
            TL['evalSlow'].append(pl['ply'])
    if not TL['slam'] and s['how'] in ('checkmate', 'resignation', 'time', 'abandonment') and n in ply_line:
        k = ply_line[n]
        for j in range(k, len(P)):
            if P[j]['kind'] != 'game':
                break
            k = j
        p = P[k]
        at = next((w['s'] for w in p['words'] if norm(w['t']).startswith(('checkmate', 'mate', 'resign', 'time'))), p['end'])
        _slam(TL, s, at, until(k), None, sfx, mate_end)
    # board marks end when the board jumps (variation in/out, back to the game, fast-forward)
    cuts = sorted([e['at'] for e in ev if not e['dur']] + [x['from'] for x in TL.get('ffs', [])])
    for key in ('arrows', 'badges', 'rings', 'highlights', 'motifs', 'cams'):
        for e in TL[key]:
            for c in cuts:
                if e['from'] < c < e['to']:
                    e['to'] = c
                    break

    # ---------- 6. who is who, the panel's move list, the eval graph ----------
    uc = a.get('userColor')

    def player(c):
        pl = a['white'] if c == 'w' else a['black']
        name = ('WHITE' if c == 'w' else 'BLACK') if uc is None else (pl['name'] if c == uc else 'Opponent')
        return dict(name=name, rating=pl['rating'], side=c)
    tc = a.get('timeControl') or ''
    base, _, inc = tc.partition('+')
    if base.isdigit():
        kind = 'Bullet' if int(base) < 180 else 'Blitz' if int(base) < 600 else 'Rapid'
        tc_text = f"{kind} · {int(base) // 60} min{f' + {inc}' if inc else ''}"
    else:
        tc_text = 'Daily' if '/' in tc else ''
    TL['meta'] = dict(orientation='b' if uc == 'b' else 'w', white=player('w'), black=player('b'), timeControl=tc_text,
                      opening=(ctx.get('opening') or {}).get('name') or a.get('opening') or '',
                      moves=[dict(ply=p['ply'], num=p['num'], color=p['color'], san=p['san'], cls=p['cls']) for p in plies],
                      curve=ctx['stats']['curve'], swings=ctx['stats']['swings'], lastPly=n,
                      fallenKing=('b' if plies[-1]['color'] == 'w' else 'w') if mate_end else None)
    TL['look'] = (look or {}).get('colors')
    TL['boards'] = boards
    TL['duration'] = _f(total) + 2
    (studio / 'public' / 'long').mkdir(parents=True, exist_ok=True)
    (studio / 'public' / 'long' / 'props.json').write_text(json.dumps(TL), encoding='utf-8')

    yt = [dict(t=0, title='Intro')]
    for c in TL['chapterCards']:
        yt.append(dict(t=round(c['from'] / FPS), title=c['title']))
    yt = [c for j, c in enumerate(yt) if j + 1 == len(yt) or yt[j + 1]['t'] - c['t'] >= 10]  # YouTube needs 10 s+
    log(f'Timeline: {total / 60:.1f} min, {len(ev)} board events, {len(TL["variations"])} variations, '
        f'{len(TL["cards"])} cards, {len(TL["thinks"])} pauses')
    return total, yt


def _side_to_move(boards: list[dict], b: int) -> str:
    """Whose move it is on board b (count back to the game position it branched from)."""
    steps = 0
    while boards[b]['main'] is None:
        b = boards[b]['prev']
        steps += 1
    return 'WHITE' if (boards[b]['main'] + steps) % 2 == 0 else 'BLACK'


def _slam(TL, s, at, to, text, sfx, mate_end):
    title = text or {'checkmate': 'CHECKMATE', 'resignation': 'RESIGNS', 'time': 'TIME!', 'abandonment': 'GAME OVER'}.get(s['how'], 'GAME OVER')
    sub = f"IN {s['totalMoves']} MOVES" if s['how'] == 'checkmate' else ''
    TL['slam'] = dict(title=title.upper(), sub=sub, **{'from': _f(at), 'to': _f(to) + 10})
    TL['shakes'].append(dict(at=_f(at), amp=14))
    TL['flashes'].append(dict(at=_f(at), color='#ffffff', strength=0.45))
    sfx(at, 'slam', 0.6)
    sfx(at, 'boom', 0.6)
    if mate_end:
        TL['kingFall'] = _f(at + 0.4)
