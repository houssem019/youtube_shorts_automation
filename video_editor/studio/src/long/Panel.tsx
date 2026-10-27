// The side panel of the long video: player cards with clocks, the move list, the cards the narration calls
// for (opening, plan, candidates, lesson, stats, graph), the "what if" line, the think timer, the eval graph.
import React from 'react';
import {Easing, Img, interpolate, spring, staticFile} from 'remotion';
import {BoardData, Card, clamp, evalOf, fmtClock, inSpan, LongData, lookOf, mainPlyOf} from './data';

const VALUE: Record<string, number> = {P: 1, N: 3, B: 3, R: 5, Q: 9, K: 0};
const START: Record<string, number> = {P: 8, N: 2, B: 2, R: 2, Q: 1};
const captured = (pos: Record<string, string>, side: 'w' | 'b') => {
  const count: Record<string, number> = {P: 0, N: 0, B: 0, R: 0, Q: 0};
  for (const p of Object.values(pos)) {
    const white = p === p.toUpperCase();
    if (white !== (side === 'w') && count[p.toUpperCase()] !== undefined) count[p.toUpperCase()]++;
  }
  const out: string[] = [];
  for (const k of ['Q', 'R', 'B', 'N', 'P']) for (let i = 0; i < Math.max(0, START[k] - count[k]); i++) out.push(k);
  return out;
};
const material = (pos: Record<string, string>, side: 'w' | 'b') =>
  Object.values(pos).reduce((acc, p) => acc + ((p === p.toUpperCase()) === (side === 'w') ? VALUE[p.toUpperCase()] : 0), 0);

const CLS: Record<string, {sym: string; color: string}> = {
  blunder: {sym: '??', color: '#E5484D'},
  mistake: {sym: '?', color: '#F5A524'},
  inaccuracy: {sym: '?!', color: '#F2D74B'},
};

export const box: React.CSSProperties = {position: 'absolute', borderRadius: 18, background: 'rgba(255,255,255,0.055)', border: '1.5px solid rgba(255,255,255,0.09)', boxShadow: '0 20px 50px rgba(0,0,0,0.35)', overflow: 'hidden'};
const kicker = (color: string): React.CSSProperties => ({fontFamily: 'Inter', fontWeight: 800, fontSize: 22, letterSpacing: 3, color});

// ---------- player card ----------
export const PlayerCard: React.FC<{d: LongData; side: 'w' | 'b'; board: BoardData; x: number; y: number; w: number; toMove: boolean}> = ({d, side, board, x, y, w, toMove}) => {
  const L = lookOf(d);
  const info = side === 'w' ? d.meta.white : d.meta.black;
  const caps = captured(board.pos, side);
  const lead = material(board.pos, side) - material(board.pos, side === 'w' ? 'b' : 'w');
  const opp = side === 'w' ? 'b' : 'w';
  const clock = board.clocks[side];
  const low = clock !== null && clock < 60;
  return (
    <div style={{...box, left: x, top: y, width: w, height: 92, display: 'flex', alignItems: 'center', gap: 18, padding: '0 22px', boxSizing: 'border-box'}}>
      <div style={{width: 60, height: 60, borderRadius: 14, background: side === 'b' ? '#2A2F3A' : '#E9E9E9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
        <Img src={staticFile(`pieces/${side}K.svg`)} style={{width: 50, height: 50}} />
      </div>
      <div style={{display: 'flex', flexDirection: 'column', lineHeight: 1.1, minWidth: 0}}>
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 30, color: 'white', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 300}}>{info.name}</div>
        <div style={{display: 'flex', alignItems: 'center', gap: 4, height: 30}}>
          {info.rating ? <span style={{fontFamily: 'Inter', fontWeight: 600, fontSize: 22, color: 'rgba(255,255,255,0.55)', marginRight: 10}}>{info.rating}</span> : null}
          {caps.map((k, i) => (
            <Img key={i} src={staticFile(`pieces/${opp}${k}.svg`)} style={{width: 28, height: 28, marginLeft: i === 0 || caps[i - 1] !== k ? 2 : -16}} />
          ))}
          {lead > 0 ? <span style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 20, color: 'rgba(255,255,255,0.75)', marginLeft: 6}}>+{lead}</span> : null}
        </div>
      </div>
      <div style={{flex: 1}} />
      {clock !== null ? (
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 34, fontVariantNumeric: 'tabular-nums', padding: '6px 16px', borderRadius: 10, background: toMove ? (low ? '#E5484D' : '#F2F2F2') : 'rgba(0,0,0,0.35)', color: toMove ? (low ? 'white' : '#111') : 'rgba(255,255,255,0.6)'}}>
          {fmtClock(clock)}
        </div>
      ) : null}
      {toMove && <div style={{position: 'absolute', left: 0, top: 14, bottom: 14, width: 5, borderRadius: 3, background: L.accent}} />}
    </div>
  );
};

// ---------- move list ----------
const MoveList: React.FC<{d: LongData; ply: number; w: number; h: number}> = ({d, ply, w, h}) => {
  const L = lookOf(d);
  const rows: {num: number; w?: (typeof d.meta.moves)[number]; b?: (typeof d.meta.moves)[number]}[] = [];
  for (const m of d.meta.moves.filter((x) => x.ply <= ply)) {
    if (m.color === 'w' || !rows.length) rows.push({num: m.num});
    rows[rows.length - 1][m.color] = m;
  }
  const RH = 46;
  const curRow = Math.max(0, rows.findIndex((r) => (r.w && r.w.ply === ply) || (r.b && r.b.ply === ply)));
  const visible = Math.floor((h - 70) / RH);
  const top = Math.max(0, curRow - visible + 1); // the latest move stays at the bottom of the list
  const cell = (m: (typeof d.meta.moves)[number] | undefined) => {
    if (!m) return <div style={{flex: 1}} />;
    const played = m.ply <= ply;
    const cur = m.ply === ply;
    const c = CLS[m.cls];
    return (
      <div style={{flex: 1, display: 'flex', alignItems: 'center', gap: 6, padding: '0 12px', height: RH - 8, borderRadius: 8, background: cur ? L.accent : 'transparent', color: cur ? '#000' : played ? 'white' : 'rgba(255,255,255,0.28)'}}>
        <span style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 26}}>{m.san}</span>
        {c && played ? <span style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 22, color: cur ? '#000' : c.color}}>{c.sym}</span> : null}
      </div>
    );
  };
  return (
    <div style={{position: 'absolute', inset: 0, padding: '22px 26px'}}>
      <div style={kicker('rgba(255,255,255,0.45)')}>MOVES</div>
      <div style={{position: 'absolute', left: 26, right: 26, top: 64, bottom: 10, overflow: 'hidden'}}>
        <div style={{translate: `0px ${-top * RH}px`}}>
          {rows.map((r, i) => (
            <div key={i} style={{display: 'flex', alignItems: 'center', height: RH}}>
              <div style={{width: 64, fontFamily: 'Inter', fontWeight: 600, fontSize: 24, color: 'rgba(255,255,255,0.4)'}}>{r.num}.</div>
              {cell(r.w)}
              {cell(r.b)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ---------- cards ----------
const stagger = (f: number, from: number, i: number, fps: number) => spring({frame: f - from - 6 - i * 7, fps, config: {damping: 14, stiffness: 180}});

const CardView: React.FC<{d: LongData; c: Card; f: number; fps: number}> = ({d, c, f, fps}) => {
  const L = lookOf(d);
  const pad: React.CSSProperties = {position: 'absolute', inset: 0, padding: '26px 30px', display: 'flex', flexDirection: 'column'};
  if (c.type === 'opening' || c.type === 'ideas') {
    const items = (c.type === 'opening' ? c.ideas : c.points) || [];
    return (
      <div style={pad}>
        <div style={kicker(L.accent)}>{c.type === 'opening' ? 'THE OPENING' : 'THE IDEA'}</div>
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: c.type === 'opening' && (c.name || '').length > 34 ? 36 : 42, color: 'white', lineHeight: 1.15, marginTop: 14}}>
          {c.type === 'opening' ? c.name : c.heading}
        </div>
        {c.type === 'opening' && c.eco ? <div style={{alignSelf: 'flex-start', marginTop: 14, fontFamily: 'Inter', fontWeight: 800, fontSize: 20, color: '#000', background: L.accent, borderRadius: 8, padding: '4px 12px'}}>ECO {c.eco}</div> : null}
        <div style={{marginTop: 26, display: 'flex', flexDirection: 'column', gap: 18}}>
          {items.map((t, i) => {
            const s = stagger(f, c.from, i, fps);
            return (
              <div key={i} style={{display: 'flex', alignItems: 'flex-start', gap: 16, opacity: s, translate: `${interpolate(s, [0, 1], [30, 0])}px 0px`}}>
                <div style={{width: 38, height: 38, borderRadius: 19, background: 'rgba(255,255,255,0.12)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Inter', fontWeight: 800, fontSize: 20, color: L.accent}}>{i + 1}</div>
                <div style={{fontFamily: 'Inter', fontWeight: 600, fontSize: 32, color: 'rgba(255,255,255,0.92)', lineHeight: 1.2}}>{t}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  if (c.type === 'candidates') {
    const items = c.items || [];
    const inList = items.some((it) => it.san === c.played);
    return (
      <div style={pad}>
        <div style={kicker(L.accent)}>ENGINE'S TOP MOVES</div>
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 40, color: 'white', marginTop: 10}}>{c.title}</div>
        <div style={{marginTop: 22, display: 'flex', flexDirection: 'column', gap: 14}}>
          {items.map((it, i) => {
            const s = stagger(f, c.from, i, fps);
            const whiteGood = it.mate !== null ? it.mate > 0 : it.cp >= 0;
            return (
              <div key={i} style={{display: 'flex', alignItems: 'center', gap: 18, height: 64, padding: '0 18px', borderRadius: 12, background: i === 0 ? 'rgba(48,199,123,0.16)' : 'rgba(255,255,255,0.06)', border: i === 0 ? '2px solid rgba(48,199,123,0.6)' : '2px solid transparent', opacity: s, translate: `${interpolate(s, [0, 1], [30, 0])}px 0px`}}>
                <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 24, color: 'rgba(255,255,255,0.45)', width: 26}}>{i + 1}</div>
                <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 36, color: 'white', flex: 1}}>{it.san}</div>
                <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 24, padding: '4px 12px', borderRadius: 8, background: whiteGood ? '#F2F2F2' : '#14161B', color: whiteGood ? '#111' : '#F2F2F2', border: '1px solid rgba(255,255,255,0.25)'}}>{it.mate ? `M${Math.abs(it.mate)}` : `${it.cp > 0 ? '+' : ''}${(it.cp / 100).toFixed(1)}`}</div>
              </div>
            );
          })}
        </div>
        {c.played && !inList ? (
          <div style={{marginTop: 18, fontFamily: 'Inter', fontWeight: 600, fontSize: 26, color: 'rgba(255,255,255,0.55)', opacity: stagger(f, c.from, items.length + 1, fps)}}>
            Played in the game: <span style={{color: '#FF8A8D', fontWeight: 800}}>{c.played}</span>
          </div>
        ) : null}
      </div>
    );
  }
  if (c.type === 'lesson') {
    const s = spring({frame: f - c.from, fps, config: {damping: 14, stiffness: 160}});
    return (
      <div style={{...pad, justifyContent: 'center'}}>
        <div style={kicker(L.accent)}>LESSON {c.num}</div>
        <div style={{fontFamily: 'Anton', fontSize: 74, lineHeight: 1.08, color: 'white', marginTop: 18, opacity: s, translate: `0px ${interpolate(s, [0, 1], [30, 0])}px`}}>{c.text}</div>
      </div>
    );
  }
  if (c.type === 'stats' && c.sides) {
    const col = (side: 'w' | 'b') => {
      const x = c.sides![side];
      const info = side === 'w' ? d.meta.white : d.meta.black;
      const acc = interpolate(f, [c.from + 6, c.from + 36], [0, x.accuracy], {...clamp, easing: Easing.out(Easing.cubic)});
      const row = (label: string, n: number, color: string, i: number) => (
        <div style={{display: 'flex', alignItems: 'center', gap: 12, opacity: stagger(f, c.from + 20, i, fps)}}>
          <div style={{width: 14, height: 14, borderRadius: 7, background: color}} />
          <div style={{fontFamily: 'Inter', fontWeight: 600, fontSize: 24, color: 'rgba(255,255,255,0.75)', flex: 1}}>{label}</div>
          <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 28, color: 'white'}}>{n}</div>
        </div>
      );
      return (
        <div style={{flex: 1, display: 'flex', flexDirection: 'column', gap: 14}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
            <Img src={staticFile(`pieces/${side}K.svg`)} style={{width: 36, height: 36}} />
            <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 24, color: 'white', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{info.name}</div>
          </div>
          <div style={{fontFamily: 'Anton', fontSize: 96, color: 'white', lineHeight: 1}}>
            {acc.toFixed(1)}
            <span style={{fontSize: 44, color: 'rgba(255,255,255,0.5)'}}>%</span>
          </div>
          {row('Blunders', x.blunders, '#E5484D', 0)}
          {row('Mistakes', x.mistakes, '#F5A524', 1)}
          {row('Inaccuracies', x.inaccuracies, '#F2D74B', 2)}
        </div>
      );
    };
    return (
      <div style={pad}>
        <div style={kicker(L.accent)}>ACCURACY</div>
        <div style={{display: 'flex', gap: 34, marginTop: 22}}>
          {col('w')}
          {col('b')}
        </div>
      </div>
    );
  }
  return null;
};

// ---------- the "what if" line ----------
const VariationBox: React.FC<{d: LongData; v: LongData['variations'][number]; board: number; f: number; fps: number}> = ({d, v, board, f, fps}) => {
  const L = lookOf(d);
  const idx = v.boards.indexOf(board);
  const ev = evalOf(d.boards[board]);
  const s = spring({frame: f - v.from, fps, config: {damping: 14, stiffness: 200}});
  return (
    <div style={{position: 'absolute', inset: 0, padding: '26px 30px', opacity: s}}>
      <div style={kicker(L.accent)}>WHAT IF</div>
      <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 30, color: 'rgba(255,255,255,0.6)', marginTop: 10}}>{v.crumb.replace('INSTEAD OF', 'Instead of')}</div>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 24}}>
        {v.boards.map((b, i) => {
          const shown = i <= idx;
          return (
            <div key={i} style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 32, padding: '8px 16px', borderRadius: 10, background: i === idx ? L.accent : shown ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.04)', color: i === idx ? '#000' : shown ? 'white' : 'rgba(255,255,255,0.25)'}}>
              {d.boards[b].label}
            </div>
          );
        })}
      </div>
      {idx >= 0 && (
        <div style={{position: 'absolute', left: 30, bottom: 26, display: 'flex', alignItems: 'center', gap: 14}}>
          <div style={{fontFamily: 'Inter', fontWeight: 600, fontSize: 24, color: 'rgba(255,255,255,0.55)'}}>Engine</div>
          <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 30, padding: '4px 14px', borderRadius: 8, background: ev.frac >= 0.5 ? '#F2F2F2' : '#14161B', color: ev.frac >= 0.5 ? '#111' : '#F2F2F2', border: '1px solid rgba(255,255,255,0.25)'}}>{ev.label}</div>
        </div>
      )}
    </div>
  );
};

// ---------- think timer ----------
const ThinkBox: React.FC<{d: LongData; t: LongData['thinks'][number]; f: number; fps: number}> = ({d, t, f, fps}) => {
  const L = lookOf(d);
  const secs = Math.round((t.to - t.from) / fps);
  const left = Math.max(1, secs - Math.floor((f - t.from) / fps));
  const ring = interpolate(f, [t.from, t.to], [1, 0], clamp);
  const s = spring({frame: f - t.from, fps, config: {damping: 12, stiffness: 200}});
  const tick = spring({frame: (f - t.from) % fps, fps, config: {damping: 10, stiffness: 300}});
  const R = 120;
  return (
    <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 26, scale: String(interpolate(s, [0, 1], [0.85, 1])), opacity: s}}>
      <svg width={R * 2 + 30} height={R * 2 + 30}>
        <circle cx={R + 15} cy={R + 15} r={R} stroke="rgba(255,255,255,0.12)" strokeWidth={16} fill="rgba(0,0,0,0.35)" />
        <circle cx={R + 15} cy={R + 15} r={R} stroke={L.accent} strokeWidth={16} fill="none" strokeDasharray={`${2 * Math.PI * R * ring} 9999`} transform={`rotate(-90 ${R + 15} ${R + 15})`} strokeLinecap="round" />
        <text x={R + 15} y={R + 55} textAnchor="middle" fontFamily="Anton" fontSize={120} fill="white" style={{scale: String(interpolate(tick, [0, 1], [1.25, 1])), transformOrigin: `${R + 15}px ${R + 15}px`} as React.CSSProperties}>
          {left}
        </text>
      </svg>
      <div style={{textAlign: 'center'}}>
        <div style={{fontFamily: 'Anton', fontSize: 58, color: 'white', letterSpacing: 1}}>{t.title}</div>
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 30, color: L.accent, letterSpacing: 2, marginTop: 4}}>{t.sub} · FIND THE BEST MOVE</div>
      </div>
    </div>
  );
};

// ---------- eval graph ----------
export const EvalGraph: React.FC<{d: LongData; ply: number; w: number; h: number; big?: boolean; f: number; from?: number}> = ({d, ply, w, h, big = false, f, from = 0}) => {
  const L = lookOf(d);
  // only the game so far: the future of the curve would give away what happens
  const now = Math.min(ply, d.meta.curve.length - 1);
  const curve = d.meta.curve.slice(0, now + 1);
  const n = Math.max(30, now + 6);
  const pad = big ? 30 : 18;
  const gw = w - pad * 2;
  const gh = h - pad * 2 - (big ? 60 : 30);
  const top = pad + (big ? 60 : 30);
  const yOf = (cp: number) => top + gh * (1 - (0.5 + 0.5 * Math.tanh(cp / 450)));
  const xOf = (i: number) => pad + (gw * i) / n;
  const draw = big ? interpolate(f, [from, from + 40], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)}) : 1;
  const upto = Math.max(0, Math.round(now * draw));
  const pts = curve.slice(0, upto + 1).map((cp, i) => `${xOf(i)},${yOf(cp)}`);
  const mid = yOf(0);
  const area = `M${xOf(0)},${top + gh} L${pts.join(' L')} L${xOf(upto)},${top + gh} Z`;
  return (
    <svg width={w} height={h} style={{position: 'absolute', left: 0, top: 0}}>
      <text x={pad} y={pad + (big ? 24 : 18)} fontFamily="Inter" fontWeight={800} fontSize={big ? 22 : 18} letterSpacing={3} fill={big ? L.accent : 'rgba(255,255,255,0.45)'}>
        EVALUATION
      </text>
      <rect x={pad} y={top} width={gw} height={gh} rx={8} fill="#14161B" />
      <path d={area} fill="#EDEDED" opacity={0.92} />
      <line x1={pad} x2={pad + gw} y1={mid} y2={mid} stroke="rgba(128,128,128,0.6)" strokeWidth={1.5} strokeDasharray="4 6" />
      {d.meta.swings
        .filter((p) => p <= upto)
        .map((p) => (
          <circle key={p} cx={xOf(p)} cy={yOf(curve[p])} r={big ? 8 : 5} fill="#E5484D" stroke="white" strokeWidth={2} />
        ))}
      {!big || draw >= 1 ? <line x1={xOf(now)} x2={xOf(now)} y1={top} y2={top + gh} stroke={L.accent} strokeWidth={3} /> : null}
      {!big || draw >= 1 ? <circle cx={xOf(now)} cy={yOf(curve[now])} r={big ? 9 : 6} fill={L.accent} stroke="#000" strokeWidth={2} /> : null}
    </svg>
  );
};

// ---------- the whole panel ----------
export const Panel: React.FC<{d: LongData; f: number; fps: number; board: number; x: number; y: number; w: number; h: number}> = ({d, f, fps, board, x, y, w, h}) => {
  const ply = mainPlyOf(d, board);
  const think = d.thinks.find((t) => inSpan(f, t));
  const v = d.variations.find((t) => inSpan(f, t) && t.boards.includes(board)) || d.variations.find((t) => inSpan(f, t));
  const card = d.cards.filter((c) => inSpan(f, c)).pop();
  const graphH = 190;
  const mainH = h - graphH - 18;
  let content: React.ReactNode;
  let key = 'moves';
  if (think) {
    content = <ThinkBox d={d} t={think} f={f} fps={fps} />;
    key = 'think' + think.from;
  } else if (v) {
    content = <VariationBox d={d} v={v} board={board} f={f} fps={fps} />;
    key = 'var' + v.from;
  } else if (card && card.type === 'graph') {
    content = <EvalGraph d={d} ply={ply} w={w} h={mainH} big f={f} from={card.from} />;
    key = 'graph' + card.from;
  } else if (card) {
    content = <CardView d={d} c={card} f={f} fps={fps} />;
    key = 'card' + card.from;
  } else {
    content = <MoveList d={d} ply={ply} w={w} h={mainH} />;
  }
  // a quick slide-in whenever the panel content changes
  const since = think ? think.from : v ? v.from : card ? card.from : Math.max(0, ...[...d.thinks, ...d.variations, ...d.cards].filter((s) => s.to <= f).map((s) => s.to));
  const s = spring({frame: f - since, fps, config: {damping: 16, stiffness: 170}});
  return (
    <>
      <div style={{...box, left: x, top: y, width: w, height: mainH}}>
        <div key={key} style={{position: 'absolute', inset: 0, opacity: interpolate(s, [0, 0.4], [0, 1], clamp), translate: `${interpolate(s, [0, 1], [40, 0])}px 0px`}}>
          {content}
        </div>
      </div>
      <div style={{...box, left: x, top: y + mainH + 18, width: w, height: graphH}}>
        <EvalGraph d={d} ply={ply} w={w} h={graphH} f={f} />
      </div>
    </>
  );
};
