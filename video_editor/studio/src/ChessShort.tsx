import React from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, continueRender, delayRender, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Board, BOARD, boardStateAt, SQ, sqXY} from './Board';
import {inSpan, LOOK, plies, positions, T} from './story';

// ---------- fonts ----------
let fontsRequested = false;
const loadFonts = () => {
  if (fontsRequested) return;
  fontsRequested = true;
  const handle = delayRender('Loading fonts');
  const faces = [
    new FontFace('Anton', `url(${staticFile('fonts/Anton.woff2')})`),
    new FontFace('Inter', `url(${staticFile('fonts/Inter800.woff2')})`, {weight: '800'}),
    new FontFace('Inter', `url(${staticFile('fonts/Inter600.woff2')})`, {weight: '600'}),
  ];
  Promise.all(faces.map((f) => f.load()))
    .then((loaded) => {
      loaded.forEach((f) => (document.fonts as unknown as {add: (x: FontFace) => void}).add(f));
      continueRender(handle);
    })
    .catch(() => continueRender(handle));
};
loadFonts();

// ---------- layout ----------
const BX = 84; // board left
const BY = 610; // board top
const VX = 80; // camera window left edge
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ---------- evaluation ----------
const toFrac = (cp: number) => 0.5 + 0.5 * Math.tanh(cp / 450);
const plyEval = (k: number) => {
  if (k === 0) return {frac: toFrac(30), label: '+0.3'};
  const pl = plies[k - 1];
  if (pl.mate) return {frac: 1, label: '1-0'};
  if (pl.cp >= 9999) return {frac: 1, label: 'M1'};
  return {frac: toFrac(pl.cp), label: `${pl.cp > 0 ? '+' : ''}${(pl.cp / 100).toFixed(1)}`};
};
const evalAt = (f: number): {frac: number; label: string} => {
  const st = T.statics.filter((x) => inSpan(f, x)).pop();
  if (st) return plyEval(st.ply);
  if (T.rewind && inSpan(f, T.rewind)) return {frac: 0.5, label: '0.0'};
  let cur = null as null | (typeof T.beats)[number];
  for (const b of T.beats) if (b.at + b.dur <= f) cur = b;
  if (!cur) return plyEval(0);
  const span = T.evalSlow.includes(cur.ply) ? 26 : 10;
  const t = interpolate(f, [cur.at + cur.dur, cur.at + cur.dur + span], [0, 1], {...clamp, easing: Easing.bezier(0.7, 0, 0.2, 1)});
  const prev = plyEval(cur.ply - 1);
  const next = plyEval(cur.ply);
  return {frac: prev.frac + (next.frac - prev.frac) * t, label: next.label};
};

const EvalBar: React.FC<{f: number}> = ({f}) => {
  const {frac, label} = evalAt(f);
  const H = BOARD;
  const whiteH = H * frac;
  const blackWinning = frac < 0.5;
  const pulse = T.evalPulse.some((p) => inSpan(f, p)) ? 0.5 + 0.5 * Math.sin(f / 3) : 0;
  return (
    <div style={{position: 'absolute', left: 22, top: BY, width: 52, height: H, borderRadius: 12, overflow: 'hidden', background: '#20242C', boxShadow: `0 0 ${20 + pulse * 40}px rgba(255,212,59,${pulse * 0.9}), 0 20px 60px rgba(0,0,0,0.5)`, outline: pulse ? `4px solid rgba(255,212,59,${0.4 + pulse * 0.6})` : undefined}}>
      <div style={{position: 'absolute', bottom: 0, left: 0, width: '100%', height: whiteH, background: '#F2F2F2'}} />
      <div
        style={{
          position: 'absolute',
          left: 0,
          width: '100%',
          textAlign: 'center',
          fontFamily: 'Inter',
          fontWeight: 800,
          fontSize: 19,
          letterSpacing: -0.5,
          color: blackWinning ? '#F2F2F2' : '#20242C',
          ...(blackWinning ? {top: 10} : {bottom: 10}),
        }}
      >
        {label}
      </div>
    </div>
  );
};

// ---------- captions: word-synced to the commentary voice ----------
const CaptionBlock: React.FC<{f: number; fps: number}> = ({f, fps}) => {
  const c = T.captions.find((x) => inSpan(f, x));
  if (!c) return null;
  return (
    <div style={{position: 'absolute', left: 70, right: 70, top: 200, height: 260, display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', alignContent: 'center', columnGap: 22, rowGap: 0}}>
      {c.words.map((w, i) => {
        const next = c.words[i + 1];
        const active = f >= w.f && (!next || f < next.f);
        const s = spring({frame: f - c.from, fps, config: {damping: 14, stiffness: 320, mass: 0.5}});
        const pop = spring({frame: f - w.f, fps, config: {damping: 10, stiffness: 400, mass: 0.4}});
        return (
          <span
            key={i}
            style={{
              fontFamily: 'Inter',
              fontWeight: 800,
              fontSize: 90,
              lineHeight: 1.15,
              textTransform: 'uppercase',
              color: active ? LOOK.accent : '#FFFFFF',
              WebkitTextStroke: '11px #000',
              paintOrder: 'stroke fill',
              textShadow: '0 6px 0 rgba(0,0,0,0.45)',
              opacity: interpolate(s, [0, 0.25], [0.01, 1], clamp),
              scale: interpolate(s, [0, 1], [0.8, 1]) * (active ? interpolate(pop, [0, 1], [1.12, 1.04]) : 1),
              translate: `0px ${interpolate(s, [0, 1], [12, 0])}px`,
            }}
          >
            {w.t.replace(/[,]$/, '')}
          </span>
        );
      })}
    </div>
  );
};

// ---------- arrows ----------
const ArrowsLayer: React.FC<{f: number}> = ({f}) => {
  const live = T.arrows.filter((a) => inSpan(f, a));
  return (
    <svg width={BOARD} height={BOARD} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
      {live.map((a, i) => {
        const A = sqXY(a.a);
        const B = sqXY(a.b);
        const draw = interpolate(f, [a.from, a.from + 9], [0, 1], {...clamp, easing: Easing.bezier(0.2, 0.8, 0.2, 1)});
        const fade = interpolate(f, [a.to - 5, a.to], [1, 0], clamp);
        const dx = B.cx - A.cx;
        const dy = B.cy - A.cy;
        const len = Math.hypot(dx, dy);
        const ux = dx / len;
        const uy = dy / len;
        const head = 46;
        const endLen = (len - SQ * 0.18) * draw;
        const ex = A.cx + ux * endLen;
        const ey = A.cy + uy * endLen;
        const lx = ex - ux * head * 0.8;
        const ly = ey - uy * head * 0.8;
        const px = -uy;
        const py = ux;
        return (
          <g key={i} opacity={0.88 * fade}>
            <line x1={A.cx} y1={A.cy} x2={lx} y2={ly} stroke={a.color} strokeWidth={24} strokeLinecap="round" strokeDasharray={a.dashed ? '2 38' : undefined} />
            {draw > 0.6 && <polygon points={`${ex},${ey} ${lx + px * head * 0.62},${ly + py * head * 0.62} ${lx - px * head * 0.62},${ly - py * head * 0.62}`} fill={a.color} />}
          </g>
        );
      })}
    </svg>
  );
};

// ---------- badges ----------
const BadgesLayer: React.FC<{f: number; fps: number}> = ({f, fps}) => (
  <>
    {T.rings
      .filter((r) => inSpan(f, r))
      .map((r, i) => {
        const {x, y} = sqXY(r.sq);
        const s = spring({frame: f - r.from, fps, config: {damping: 12, stiffness: 200}});
        return <div key={'r' + i} style={{position: 'absolute', left: x + 4, top: y + 4, width: SQ - 8, height: SQ - 8, borderRadius: SQ, border: `8px solid ${r.color}`, boxShadow: `0 0 24px ${r.color}`, scale: interpolate(s, [0, 1], [1.8, 1]), opacity: interpolate(s, [0, 0.3], [0.01, 1], clamp)}} />;
      })}
    {T.badges
      .filter((b) => inSpan(f, b))
      .map((b, i) => {
        const {x, y} = sqXY(b.sq);
        const s = spring({frame: f - b.from, fps, config: {damping: 9, stiffness: 260, mass: 0.5}});
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x + SQ - 46,
              top: y - 22,
              width: 70,
              height: 70,
              borderRadius: 35,
              background: b.color,
              border: '5px solid white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'Inter',
              fontWeight: 800,
              fontSize: 36,
              color: 'white',
              letterSpacing: -2,
              boxShadow: '0 8px 20px rgba(0,0,0,0.45)',
              scale: interpolate(s, [0, 1], [0.02, 1]), opacity: interpolate(s, [0, 0.15], [0, 1], clamp),
            }}
          >
            {b.text}
          </div>
        );
      })}
  </>
);

// ---------- player strips: name, rating, captured pieces, material lead ----------
const VALUE: Record<string, number> = {P: 1, N: 3, B: 3, R: 5, Q: 9, K: 0};
const START: Record<string, number> = {P: 8, N: 2, B: 2, R: 2, Q: 1};
const capturedBy = (pos: Record<string, string>, side: 'w' | 'b') => {
  // pieces of the other colour that are missing from the board
  const count: Record<string, number> = {P: 0, N: 0, B: 0, R: 0, Q: 0};
  for (const p of Object.values(pos)) {
    const isWhite = p === p.toUpperCase();
    if ((side === 'w' && !isWhite) || (side === 'b' && isWhite)) if (count[p.toUpperCase()] !== undefined) count[p.toUpperCase()]++;
  }
  const out: string[] = [];
  for (const k of ['Q', 'R', 'B', 'N', 'P']) for (let i = 0; i < Math.max(0, START[k] - count[k]); i++) out.push(k);
  return out;
};
const material = (pos: Record<string, string>, side: 'w' | 'b') =>
  Object.values(pos).reduce((acc, p) => acc + ((p === p.toUpperCase()) === (side === 'w') ? VALUE[p.toUpperCase()] : 0), 0);

const Strip: React.FC<{top: number; side: 'b' | 'w'; ply: number}> = ({top, side, ply}) => {
  const pos = positions[Math.min(ply, positions.length - 1)];
  const info = side === 'w' ? T.meta.white : T.meta.black;
  const caps = capturedBy(pos, side);
  const lead = material(pos, side) - material(pos, side === 'w' ? 'b' : 'w');
  const opp = side === 'w' ? 'b' : 'w';
  return (
    <div style={{position: 'absolute', left: BX, width: BOARD, top, height: 84, display: 'flex', alignItems: 'center', gap: 18}}>
      <div style={{width: 72, height: 72, borderRadius: 16, background: side === 'b' ? '#2A2F3A' : '#E9E9E9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0}}>
        <Img src={staticFile(`pieces/${side}K.svg`)} style={{width: 60, height: 60}} />
      </div>
      <div style={{display: 'flex', flexDirection: 'column', lineHeight: 1.05}}>
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 36, color: 'white', letterSpacing: 0.5, maxWidth: 430, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{info.name}</div>
        {info.rating ? <div style={{fontFamily: 'Inter', fontWeight: 600, fontSize: 24, color: 'rgba(255,255,255,0.6)'}}>{info.rating}</div> : null}
      </div>
      <div style={{flex: 1}} />
      <div style={{display: 'flex', alignItems: 'center'}}>
        {caps.map((k, i) => (
          <Img key={i} src={staticFile(`pieces/${opp}${k}.svg`)} style={{width: 44, height: 44, marginLeft: i === 0 || caps[i - 1] !== k ? 4 : -22}} />
        ))}
        {lead > 0 ? <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 28, color: 'rgba(255,255,255,0.8)', marginLeft: 10}}>+{lead}</div> : null}
      </div>
    </div>
  );
};

// ---------- bottom ticker: current move, or the pause countdown ----------
const Ticker: React.FC<{f: number; fps: number}> = ({f, fps}) => {
  const top = BY + BOARD + 118;
  const cd = T.countdown;
  if (cd && inSpan(f, cd)) {
    const per = (cd.to - cd.from) / 3;
    const idx = Math.min(2, Math.floor((f - cd.from) / per));
    const n = 3 - idx;
    const s = spring({frame: f - (cd.from + idx * per), fps, config: {damping: 10, stiffness: 200}});
    const ring = interpolate(f, [cd.from, cd.to], [1, 0], clamp);
    return (
      <div style={{position: 'absolute', left: 0, right: 0, top: top - 22, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 26}}>
        <svg width={120} height={120}>
          <circle cx={60} cy={60} r={52} stroke="rgba(255,255,255,0.15)" strokeWidth={10} fill="#111" />
          <circle cx={60} cy={60} r={52} stroke={LOOK.accent} strokeWidth={10} fill="none" strokeDasharray={`${2 * Math.PI * 52 * ring} 999`} transform="rotate(-90 60 60)" strokeLinecap="round" />
          <text x={60} y={80} textAnchor="middle" fontFamily="Anton" fontSize={60} fill="white" style={{scale: interpolate(s, [0, 1], [1.5, 1]), transformOrigin: '60px 60px'} as React.CSSProperties}>
            {n}
          </text>
        </svg>
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 38, color: 'white', lineHeight: 1.2}}>
          {cd.title}
          <br />
          <span style={{color: LOOK.accent}}>{cd.sub}</span>
        </div>
      </div>
    );
  }
  if (T.statics.some((x) => inSpan(f, x)) || (T.rewind && inSpan(f, T.rewind))) return null;
  let cur = null as null | (typeof T.beats)[number];
  for (const b of T.beats) if (b.at <= f) cur = b;
  if (!cur) return null;
  const ff = (T.ffs || []).find((x) => inSpan(f, x));
  if (ff) {
    const s = spring({frame: f - ff.from, fps, config: {damping: 12, stiffness: 300}});
    const num = plies[Math.min(Math.max(cur.ply, ff.fromPly), ff.toPly) - 1].num;
    return (
      <div style={{position: 'absolute', left: 0, right: 0, top, display: 'flex', justifyContent: 'center'}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 18, background: LOOK.accent, borderRadius: 999, padding: '10px 34px', scale: String(interpolate(s, [0, 1], [0.6, 1])), boxShadow: `0 0 40px ${LOOK.accent}88`}}>
          <div style={{display: 'flex', translate: `${(f % 6) * 2}px 0px`}}>
            {[0, 1].map((i) => (
              <div key={i} style={{width: 0, height: 0, borderTop: '20px solid transparent', borderBottom: '20px solid transparent', borderLeft: '30px solid #000'}} />
            ))}
          </div>
          <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 40, color: '#000', fontVariantNumeric: 'tabular-nums', minWidth: 200}}>MOVE {num}</div>
        </div>
      </div>
    );
  }
  const pl = plies[cur.ply - 1];
  const bad = T.meta.badPlies.includes(cur.ply);
  const s = spring({frame: f - cur.at, fps, config: {damping: 14, stiffness: 260}});
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top, display: 'flex', justifyContent: 'center'}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 14, background: bad ? '#E5484D' : 'rgba(255,255,255,0.1)', border: '2px solid rgba(255,255,255,0.25)', borderRadius: 999, padding: '10px 28px', translate: `0px ${interpolate(s, [0, 1], [14, 0])}px`}}>
        <div style={{width: 22, height: 22, borderRadius: 11, background: pl.color === 'w' ? '#F2F2F2' : '#111', border: '2px solid #888'}} />
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 40, color: 'white'}}>
          {pl.num}
          {pl.color === 'w' ? '.' : '...'} {pl.san}
          {bad ? '??' : ''}
        </div>
      </div>
    </div>
  );
};

// ---------- camera ----------
const cameraAt = (f: number) => {
  for (const c of T.cams) {
    if (f >= c.from && f < c.to) {
      const env = Math.min(
        interpolate(f, [c.from, c.from + 10], [0, 1], {...clamp, easing: Easing.bezier(0.3, 0, 0.2, 1)}),
        interpolate(f, [c.to - 10, c.to], [1, 0], {...clamp, easing: Easing.bezier(0.6, 0, 0.7, 1)}),
      );
      const {cx, cy} = sqXY(c.sq);
      const sx = BX + cx;
      const sy = BY + cy;
      // zoom around the square and drift it toward the middle of the board area
      return {scale: 1 + (c.peak - 1) * env, ox: sx, oy: sy, tx: (BX + BOARD / 2 - sx) * 0.42 * env, ty: (BY + BOARD / 2 - sy) * 0.42 * env};
    }
  }
  return {scale: 1, ox: 540, oy: BY + BOARD / 2, tx: 0, ty: 0};
};

const shakeAt = (f: number) => {
  let x = 0;
  let y = 0;
  for (const s of T.shakes) {
    if (f >= s.at && f < s.at + 30) {
      const k = s.amp * Math.exp(-(f - s.at) / 5);
      x += k * Math.sin(f * 2.3 + s.at);
      y += k * Math.cos(f * 3.1 + s.at);
    }
  }
  return {x, y};
};

// ---------- the composition ----------
export const ChessShort: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const state = boardStateAt(f);
  const cam = cameraAt(f);
  const shake = shakeAt(f);
  const kingFall = state.fallenStatic ? 1 : T.kingFall === null ? 0 : interpolate(f, [T.kingFall, T.kingFall + 22], [0, 1], {...clamp, easing: Easing.bezier(0.5, 0, 0.9, 0.6)});
  const rewinding = !!T.rewind && inSpan(f, T.rewind);
  const transition = T.rewind?.style || 'tape';
  const tape = rewinding && transition === 'tape';
  const hl = T.headline && inSpan(f, T.headline) ? T.headline : null;
  const ffing = (T.ffs || []).some((x) => inSpan(f, x));

  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 45%, ${LOOK.bg[0]} 0%, ${LOOK.bg[1]} 60%, ${LOOK.bg[2]} 100%)`}}>
      {/* subtle texture */}
      <AbsoluteFill style={{backgroundImage: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.025) 0 2px, transparent 2px 22px)'}} />

      <AbsoluteFill style={{translate: `${shake.x + (tape ? Math.sin(f * 7) * 14 : 0)}px ${shake.y}px`, transform: tape ? `skewX(${Math.sin(f * 5) * 3}deg)` : undefined}}>
        <Strip top={BY - 100} side={T.meta.orientation === 'b' ? 'w' : 'b'} ply={state.ply} />
        <Strip top={BY + BOARD + 16} side={T.meta.orientation} ply={state.ply} />
        {/* camera window: the board can zoom and drift inside it without covering the rest */}
        <div style={{position: 'absolute', left: VX, top: BY - 8, width: 1080 - VX, height: BOARD + 16, overflow: 'hidden', borderRadius: 18, boxShadow: ffing ? `0 0 0 6px ${LOOK.accent}, 0 0 60px ${LOOK.accent}66` : undefined}}>
          <div style={{position: 'absolute', left: BX - VX, top: 8, width: BOARD, height: BOARD, scale: String(cam.scale), transformOrigin: `${cam.ox - BX}px ${cam.oy - BY}px`, translate: `${cam.tx}px ${cam.ty}px`}}>
            <Board state={state} kingFall={kingFall} />
            <ArrowsLayer f={f} />
            <BadgesLayer f={f} fps={fps} />
          </div>
        </div>
        <EvalBar f={f} />
        <Ticker f={f} fps={fps} />

        {/* headline opener: dimmed board + one big line built from the game facts */}
        {hl &&
          (() => {
            const s = spring({frame: f - hl.from, fps, config: {damping: 13, stiffness: 260, mass: 0.6}});
            const out = interpolate(f, [hl.to - 8, hl.to], [1, 0], clamp);
            return (
              <div style={{position: 'absolute', left: VX, top: BY - 8, width: 1080 - VX, height: BOARD + 16, borderRadius: 18, background: `rgba(0,0,0,${0.55 * Math.min(1, s) * out})`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                <div style={{fontFamily: 'Anton', fontSize: hl.text.length > 12 ? 128 : 156, lineHeight: 1.02, textAlign: 'center', maxWidth: 900, color: LOOK.accent, WebkitTextStroke: '14px #000', paintOrder: 'stroke fill', textShadow: '0 12px 0 rgba(0,0,0,0.55)', letterSpacing: 2, scale: interpolate(s, [0, 1], [0.55, 1]), opacity: interpolate(s, [0, 0.25], [0, 1], clamp) * out}}>
                  {hl.text}
                </div>
              </div>
            );
          })()}

        <CaptionBlock f={f} fps={fps} />

        {/* CHECKMATE slam */}
        {T.slam && inSpan(f, T.slam) && (
          <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', translate: `0px ${BY + BOARD - 380 - 960}px`}}>
            {(() => {
              const s = spring({frame: f - T.slam!.from, fps, config: {damping: 12, stiffness: 300, mass: 0.7}});
              return (
                <div style={{textAlign: 'center', scale: interpolate(s, [0, 1], [3, 1]), opacity: interpolate(s, [0, 0.3], [0, 1], clamp), rotate: '-7deg'}}>
                  <div style={{fontFamily: 'Anton', fontSize: 190, color: LOOK.slam, WebkitTextStroke: '16px #000', paintOrder: 'stroke fill', textShadow: '0 14px 0 rgba(0,0,0,0.6)', lineHeight: 1}}>{T.slam!.title}</div>
                  <div style={{fontFamily: 'Anton', fontSize: 84, color: 'white', WebkitTextStroke: '10px #000', paintOrder: 'stroke fill', marginTop: 6}}>{T.slam!.sub}</div>
                </div>
              );
            })()}
          </AbsoluteFill>
        )}
      </AbsoluteFill>

      {/* rewind look: "tape" (original), "clean" (a MOVE 1 label), "flash" (just the flash + fast rewind) */}
      {rewinding && transition === 'clean' && (
        <div style={{position: 'absolute', left: 0, right: 0, top: 150, display: 'flex', justifyContent: 'center'}}>
          <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 52, color: '#000', background: LOOK.accent, borderRadius: 999, padding: '10px 40px', letterSpacing: 1, scale: String(spring({frame: f - T.rewind!.from, fps, config: {damping: 12, stiffness: 300}}))}}>{T.rewind!.label || 'BACK TO MOVE 1'}</div>
        </div>
      )}
      {tape && (
        <AbsoluteFill style={{backgroundImage: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.35) 0 3px, transparent 3px 7px)', mixBlendMode: 'multiply'}}>
          <div style={{position: 'absolute', left: 60, top: 160, display: 'flex', alignItems: 'center', gap: 16}}>
            {[0, 1].map((i) => (
              <div key={i} style={{width: 0, height: 0, borderTop: '34px solid transparent', borderBottom: '34px solid transparent', borderRight: '52px solid white'}} />
            ))}
            <div style={{fontFamily: 'Anton', fontSize: 90, color: 'white', marginLeft: 12}}>REWIND</div>
          </div>
        </AbsoluteFill>
      )}

      {/* flashes */}
      {T.flashes.map((fl, i) =>
        f >= fl.at && f < fl.at + 10 ? <AbsoluteFill key={i} style={{background: fl.color, opacity: interpolate(f, [fl.at, fl.at + 10], [fl.strength, 0], clamp)}} /> : null,
      )}

      {/* vignette */}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)', pointerEvents: 'none'}} />

      {/* commentary */}
      <Audio src={staticFile('voice.wav')} volume={1} />
      {/* move sounds */}
      {T.beats
        .filter((b) => b.ply !== 37 && !b.ff)
        .map((b, i) => {
          const pl = plies[b.ply - 1];
          const src = pl.captured ? 'capture' : b.ply % 2 ? 'move1' : 'move2';
          return <Audio key={'m' + i} from={b.at + b.dur - 2} src={staticFile(`sfx/${src}.wav`)} volume={pl.captured ? 0.45 : 0.35} premountFor={fps} />;
        })}
      {T.sfx.map((s, i) => (
        <Audio key={'s' + i} from={s.at} src={staticFile(`sfx/${s.src}.wav`)} volume={s.vol} premountFor={fps} />
      ))}
    </AbsoluteFill>
  );
};
