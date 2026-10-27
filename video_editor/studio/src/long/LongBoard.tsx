// The board for the long video: pieces, move animation, last-move/check marks, and the board-level
// effects (arrows, badges, rings, highlights, tactic callouts). Sized by `size`; works for any board state.
import React from 'react';
import {Easing, Img, interpolate, spring, staticFile} from 'remotion';
import {BoardView, clamp, inSpan, LongData, lookOf} from './data';

const pieceCode = (p: string) => (p === p.toUpperCase() ? 'w' : 'b') + p.toUpperCase();

export const makeXY = (size: number, flip: boolean) => {
  const sq = size / 8;
  return (s: string) => {
    const f = flip ? 7 - (s.charCodeAt(0) - 97) : s.charCodeAt(0) - 97;
    const r = flip ? 9 - Number(s[1]) : Number(s[1]);
    return {x: f * sq, y: (8 - r) * sq, cx: f * sq + sq / 2, cy: (8 - r) * sq + sq / 2};
  };
};

type Props = {d: LongData; f: number; fps: number; view: BoardView; size: number; kingFall?: number; effects?: boolean; variation?: boolean};

export const LongBoard: React.FC<Props> = ({d, f, fps, view, size, kingFall = 0, effects = true, variation = false}) => {
  const L = lookOf(d);
  const flip = d.meta.orientation === 'b';
  const xy = makeXY(size, flip);
  const SQ = size / 8;
  const target = d.boards[view.board];
  const animating = view.prev !== null && view.t < 1 && !!target.anim;
  const shown = animating ? d.boards[view.prev!] : target;

  type PV = {key: string; piece: string; x: number; y: number; opacity: number};
  let pieces: PV[];
  if (animating) {
    const moving = new Map(target.anim!.map(([a, b]) => [a, b]));
    pieces = Object.entries(shown.pos).map(([s, p]) => {
      const from = xy(s);
      const dest = moving.get(s);
      if (dest) {
        const to = xy(dest);
        return {key: s, piece: pieceCode(p), x: from.x + (to.x - from.x) * view.t, y: from.y + (to.y - from.y) * view.t, opacity: 1};
      }
      const cap = target.captured === s;
      return {key: s, piece: pieceCode(p), x: from.x, y: from.y, opacity: cap ? 1 - Math.min(1, Math.max(0, (view.t - 0.55) * 2.5)) : 1};
    });
    // promotion: the pawn becomes the new piece as it lands
    const dest = target.anim![0][1];
    pieces = pieces.map((p) => (p.key === target.anim![0][0] && view.t > 0.85 && target.pos[dest] ? {...p, piece: pieceCode(target.pos[dest])} : p));
    pieces.sort((a, b) => (moving.has(a.key) ? 1 : 0) - (moving.has(b.key) ? 1 : 0));
  } else {
    pieces = Object.entries(target.pos).map(([s, p]) => ({key: s, piece: pieceCode(p), ...xy(s), opacity: 1}));
  }
  const last = animating ? target.last : target.last;
  const check = animating ? null : target.check;
  const fallen = !animating && target.mate && d.meta.fallenKing ? `${d.meta.fallenKing}K` : null;

  const files = flip ? 'hgfedcba' : 'abcdefgh';
  const ranks = flip ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
  const cells = [];
  for (let r = 0; r < 8; r++)
    for (let c = 0; c < 8; c++) cells.push(<rect key={`${c}${r}`} x={c * SQ} y={r * SQ} width={SQ} height={SQ} fill={(r + c) % 2 === 0 ? L.light : L.dark} />);
  const fs = Math.round(size / 44);

  return (
    <div style={{position: 'absolute', left: 0, top: 0, width: size, height: size, borderRadius: 14, overflow: 'hidden'}}>
      <svg width={size} height={size} style={{position: 'absolute', left: 0, top: 0}}>
        {cells}
        {files.split('').map((c, i) => (
          <text key={c} x={i * SQ + SQ - 7} y={size - 7} textAnchor="end" fontFamily="Inter" fontWeight={800} fontSize={fs} fill={i % 2 === 0 ? L.light : L.dark}>
            {c}
          </text>
        ))}
        {ranks.map((n, i) => (
          <text key={n} x={6} y={i * SQ + fs + 4} fontFamily="Inter" fontWeight={800} fontSize={fs} fill={i % 2 === 0 ? L.dark : L.light}>
            {n}
          </text>
        ))}
      </svg>
      {variation && <div style={{position: 'absolute', inset: 0, background: L.accent, opacity: 0.07}} />}
      {last &&
        last.map((s) => {
          const {x, y} = xy(s);
          return <div key={'hl' + s} style={{position: 'absolute', left: x, top: y, width: SQ, height: SQ, background: 'rgba(255, 212, 59, 0.42)'}} />;
        })}
      {effects &&
        d.highlights
          .filter((h) => inSpan(f, h))
          .flatMap((h, i) =>
            h.squares.map((s) => {
              const {x, y} = xy(s);
              const a = interpolate(f, [h.from, h.from + 8, h.to - 6, h.to], [0, 0.5, 0.5, 0], clamp);
              return <div key={`h${i}${s}`} style={{position: 'absolute', left: x, top: y, width: SQ, height: SQ, background: h.color, opacity: a}} />;
            }),
          )}
      {check && (
        <div style={{position: 'absolute', left: xy(check).x, top: xy(check).y, width: SQ, height: SQ, background: 'radial-gradient(circle, rgba(255,40,40,0.95) 0%, rgba(255,40,40,0.55) 45%, rgba(255,40,40,0) 75%)'}} />
      )}
      {pieces.map((p) => {
        const isFallen = fallen === p.piece;
        return (
          <Img
            key={p.key}
            src={staticFile(`pieces/${p.piece}.svg`)}
            style={{
              position: 'absolute',
              left: p.x,
              top: p.y,
              width: SQ,
              height: SQ,
              opacity: p.opacity,
              rotate: isFallen ? `${interpolate(kingFall, [0, 1], [0, 88])}deg` : undefined,
              translate: isFallen ? `${interpolate(kingFall, [0, 1], [0, -8])}px ${interpolate(kingFall, [0, 1], [0, 14])}px` : undefined,
              filter: 'drop-shadow(0 5px 5px rgba(0,0,0,0.35))',
            }}
          />
        );
      })}
      {effects && <Marks d={d} f={f} fps={fps} size={size} xy={xy} />}
    </div>
  );
};

// arrows, rings, badges and tactic callouts on top of the pieces
const Marks: React.FC<{d: LongData; f: number; fps: number; size: number; xy: ReturnType<typeof makeXY>}> = ({d, f, fps, size, xy}) => {
  const SQ = size / 8;
  const L = lookOf(d);
  const head = SQ * 0.42;
  const arrow = (A: {cx: number; cy: number}, B: {cx: number; cy: number}, color: string, dashed: boolean, draw: number, alpha: number, key: string, width = SQ * 0.2) => {
    const dx = B.cx - A.cx;
    const dy = B.cy - A.cy;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len;
    const uy = dy / len;
    const endLen = (len - SQ * 0.18) * draw;
    const ex = A.cx + ux * endLen;
    const ey = A.cy + uy * endLen;
    const lx = ex - ux * head * 0.8;
    const ly = ey - uy * head * 0.8;
    const px = -uy;
    const py = ux;
    return (
      <g key={key} opacity={alpha}>
        <line x1={A.cx} y1={A.cy} x2={lx} y2={ly} stroke={color} strokeWidth={width} strokeLinecap="round" strokeDasharray={dashed ? `2 ${SQ * 0.36}` : undefined} />
        {draw > 0.6 && <polygon points={`${ex},${ey} ${lx + px * head * 0.62},${ly + py * head * 0.62} ${lx - px * head * 0.62},${ly - py * head * 0.62}`} fill={color} />}
      </g>
    );
  };
  return (
    <>
      <svg width={size} height={size} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
        {d.arrows
          .filter((a) => inSpan(f, a))
          .map((a, i) => {
            const draw = interpolate(f, [a.from, a.from + 10], [0, 1], {...clamp, easing: Easing.bezier(0.2, 0.8, 0.2, 1)});
            const fade = interpolate(f, [a.to - 6, a.to], [1, 0], clamp);
            return arrow(xy(a.a), xy(a.b), a.color, a.dashed, draw, 0.86 * fade, 'a' + i);
          })}
        {d.motifs
          .filter((m) => inSpan(f, m))
          .flatMap((m, i) => {
            const draw = interpolate(f, [m.from + 4, m.from + 16], [0, 1], {...clamp, easing: Easing.bezier(0.2, 0.8, 0.2, 1)});
            const fade = interpolate(f, [m.to - 6, m.to], [1, 0], clamp);
            return m.targets.map((t, j) => arrow(xy(m.sq), xy(t), L.accent, false, draw, 0.9 * fade, `m${i}${j}`, SQ * 0.11));
          })}
      </svg>
      {[...d.rings.filter((r) => inSpan(f, r)).map((r) => ({sq: r.sq, color: r.color, from: r.from})),
        ...d.motifs.filter((m) => inSpan(f, m)).flatMap((m) => m.targets.map((t) => ({sq: t, color: L.accent, from: m.from + 10})))].map((r, i) => {
        const {x, y} = xy(r.sq);
        const s = spring({frame: f - r.from, fps, config: {damping: 12, stiffness: 200}});
        return <div key={'r' + i} style={{position: 'absolute', left: x + 4, top: y + 4, width: SQ - 8, height: SQ - 8, borderRadius: SQ, border: `${Math.round(SQ / 14)}px solid ${r.color}`, boxShadow: `0 0 18px ${r.color}`, scale: String(interpolate(s, [0, 1], [1.8, 1])), opacity: interpolate(s, [0, 0.3], [0.01, 1], clamp)}} />;
      })}
      {d.motifs
        .filter((m) => inSpan(f, m))
        .map((m, i) => {
          const {cx, y} = xy(m.sq);
          const s = spring({frame: f - m.from, fps, config: {damping: 11, stiffness: 240, mass: 0.6}});
          const above = y > SQ * 0.9;
          return (
            <div key={'mt' + i} style={{position: 'absolute', left: cx, top: above ? y - SQ * 0.62 : y + SQ * 1.06, translate: '-50% 0', background: L.accent, color: '#000', fontFamily: 'Inter', fontWeight: 800, fontSize: SQ * 0.3, letterSpacing: 1, padding: `${SQ * 0.05}px ${SQ * 0.16}px`, borderRadius: 999, whiteSpace: 'nowrap', boxShadow: '0 8px 20px rgba(0,0,0,0.45)', scale: String(interpolate(s, [0, 1], [0.3, 1])), opacity: interpolate(s, [0, 0.2], [0, 1], clamp)}}>
              {m.name}
            </div>
          );
        })}
      {d.badges
        .filter((b) => inSpan(f, b))
        .map((b, i) => {
          const {x, y} = xy(b.sq);
          const s = spring({frame: f - b.from, fps, config: {damping: 9, stiffness: 260, mass: 0.5}});
          const r = SQ * 0.56;
          return (
            <div key={'b' + i} style={{position: 'absolute', left: x + SQ - r * 0.66, top: y - r * 0.3, width: r, height: r, borderRadius: r, background: b.color, border: `${Math.max(3, SQ / 28)}px solid white`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Inter', fontWeight: 800, fontSize: r * 0.5, color: 'white', letterSpacing: -1, boxShadow: '0 6px 16px rgba(0,0,0,0.45)', scale: String(interpolate(s, [0, 1], [0.02, 1])), opacity: interpolate(s, [0, 0.15], [0, 1], clamp)}}>
              {b.text}
            </div>
          );
        })}
    </>
  );
};
