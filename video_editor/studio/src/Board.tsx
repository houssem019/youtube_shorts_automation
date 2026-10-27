import React from 'react';
import {Easing, Img, interpolate, staticFile} from 'remotion';
import {inSpan, LOOK, plies, positions, T} from './story';

export const BOARD = 968;
export const SQ = BOARD / 8;
export const LIGHT = LOOK.light;
export const DARK = LOOK.dark;

const FLIP = T.meta.orientation === 'b';
export const sqXY = (sq: string) => {
  const f = FLIP ? 7 - (sq.charCodeAt(0) - 97) : sq.charCodeAt(0) - 97;
  const r = FLIP ? 9 - Number(sq[1]) : Number(sq[1]);
  return {x: f * SQ, y: (8 - r) * SQ, cx: f * SQ + SQ / 2, cy: (8 - r) * SQ + SQ / 2};
};

type PieceView = {key: string; piece: string; x: number; y: number; opacity: number; rotate: number};
export type BoardState = {
  pieces: PieceView[];
  lastMove: [string, string] | null;
  check: string | null;
  mate: boolean;
  ply: number; // ply whose result is shown (0 = start)
  animating: boolean;
};

const pieceCode = (p: string) => (p === p.toUpperCase() ? 'w' : 'b') + p.toUpperCase();

const staticState = (k: number): BoardState => {
  const pos = positions[k];
  const pl = k > 0 ? plies[k - 1] : null;
  return {
    pieces: Object.entries(pos).map(([sq, p]) => ({key: sq, piece: pieceCode(p), ...sqXY(sq), opacity: 1, rotate: 0})),
    lastMove: pl ? (pl.moves[0] as [string, string]) : null,
    check: pl ? pl.check : null,
    mate: pl ? pl.mate : false,
    ply: k,
    animating: false,
  };
};

export const boardStateAt = (f: number): BoardState & {fallenStatic: boolean} => {
  const st = T.statics.filter((x) => inSpan(f, x)).pop();
  if (st) return {...staticState(st.ply), fallenStatic: st.fallen};
  if (T.rewind && inSpan(f, T.rewind)) {
    const k = Math.round(interpolate(f, [T.rewind.from, T.rewind.to - 3], [T.rewind.fromPly, T.rewind.toPly ?? 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
    return {...staticState(k), lastMove: null, check: null, mate: false, fallenStatic: false};
  }
  let current = null as null | (typeof T.beats)[number];
  for (const b of T.beats) if (b.at <= f) current = b;
  if (!current) return {...staticState(0), fallenStatic: false};
  const k = current.ply;
  const p = (f - current.at) / current.dur;
  if (p >= 1) return {...staticState(k), fallenStatic: false};

  const t = Easing.bezier(0.33, 0, 0.15, 1)(Math.max(0, p));
  const pl = plies[k - 1];
  const before = positions[k - 1];
  const moving = new Map(pl.moves.map(([a, b]) => [a, b]));
  const pieces: PieceView[] = Object.entries(before).map(([sq, piece]) => {
    const from = sqXY(sq);
    const dest = moving.get(sq);
    if (dest) {
      const to = sqXY(dest);
      return {key: sq, piece: pieceCode(piece), x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t, opacity: 1, rotate: 0};
    }
    const captured = pl.captured === sq;
    return {key: sq, piece: pieceCode(piece), x: from.x, y: from.y, opacity: captured ? 1 - Math.min(1, Math.max(0, (t - 0.55) * 2.5)) : 1, rotate: 0};
  });
  pieces.sort((a, b) => (moving.has(a.key) ? 1 : 0) - (moving.has(b.key) ? 1 : 0));
  return {pieces, lastMove: pl.moves[0] as [string, string], check: null, mate: false, ply: k, animating: true, fallenStatic: false};
};

const Squares: React.FC = () => {
  const cells = [];
  for (let r = 0; r < 8; r++)
    for (let f = 0; f < 8; f++) {
      const light = (r + f) % 2 === 0;
      cells.push(<rect key={`${f}${r}`} x={f * SQ} y={r * SQ} width={SQ} height={SQ} fill={light ? LIGHT : DARK} />);
    }
  const files = FLIP ? 'hgfedcba' : 'abcdefgh';
  return (
    <svg width={BOARD} height={BOARD} style={{position: 'absolute', left: 0, top: 0}}>
      {cells}
      {files.split('').map((c, i) => (
        <text key={c} x={i * SQ + SQ - 10} y={BOARD - 8} textAnchor="end" fontFamily="Inter" fontWeight={800} fontSize={22} fill={i % 2 === 0 ? LIGHT : DARK}>
          {c}
        </text>
      ))}
      {(FLIP ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1]).map((n, i) => (
        <text key={n} x={8} y={i * SQ + 28} fontFamily="Inter" fontWeight={800} fontSize={22} fill={i % 2 === 0 ? DARK : LIGHT}>
          {n}
        </text>
      ))}
    </svg>
  );
};

export const Board: React.FC<{state: BoardState; kingFall: number}> = ({state, kingFall}) => {
  const hl = state.lastMove;
  return (
    <div style={{position: 'absolute', width: BOARD, height: BOARD, borderRadius: 18, overflow: 'hidden', boxShadow: '0 30px 80px rgba(0,0,0,0.55)'}}>
      <Squares />
      {hl &&
        hl.map((sq) => {
          const {x, y} = sqXY(sq);
          return <div key={'hl' + sq} style={{position: 'absolute', left: x, top: y, width: SQ, height: SQ, background: 'rgba(255, 212, 59, 0.45)'}} />;
        })}
      {state.check && (
        <div
          style={{
            position: 'absolute',
            left: sqXY(state.check).x,
            top: sqXY(state.check).y,
            width: SQ,
            height: SQ,
            background: 'radial-gradient(circle, rgba(255,40,40,0.95) 0%, rgba(255,40,40,0.55) 45%, rgba(255,40,40,0) 75%)',
          }}
        />
      )}
      {state.pieces.map((p) => {
        const isFallen = state.mate && !!T.meta.fallenKing && p.piece === `${T.meta.fallenKing}K`;
        const rot = isFallen ? interpolate(kingFall, [0, 1], [0, 88]) : p.rotate;
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
              rotate: `${rot}deg`,
              translate: isFallen ? `${interpolate(kingFall, [0, 1], [0, -10])}px ${interpolate(kingFall, [0, 1], [0, 18])}px` : undefined,
              filter: 'drop-shadow(0 6px 6px rgba(0,0,0,0.35))',
            }}
          />
        );
      })}
    </div>
  );
};
