// The long (16:9) video: board + eval bar on the left, panel on the right, with the cold open, title sequence,
// chapter cards, "what if" lines, think pauses, the finish and the end screen drawn over it.
import React from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {boardAt, clamp, evalAt, inSpan, loadFonts, LongData, lookOf} from './data';
import {LongBoard, makeXY} from './LongBoard';
import {Panel, PlayerCard} from './Panel';

loadFonts();

const BOARD = 880;
const BX = 200;
const BY = 110;
const PX = 1124;
const PW = 660;

const EvalBar: React.FC<{d: LongData; f: number}> = ({d, f}) => {
  const {frac, label} = evalAt(d, f);
  const L = lookOf(d);
  const flip = d.meta.orientation === 'b';
  const whiteFrac = flip ? 1 - frac : frac; // the bottom part belongs to the side at the bottom
  const pulse = d.evalPulse.some((p) => inSpan(f, p)) ? 0.5 + 0.5 * Math.sin(f / 3) : 0;
  const bottomColor = flip ? '#20242C' : '#F2F2F2';
  const topColor = flip ? '#F2F2F2' : '#20242C';
  const bottomWinning = flip ? frac < 0.5 : frac >= 0.5;
  return (
    <div style={{position: 'absolute', left: BX - 64, top: BY, width: 44, height: BOARD, borderRadius: 10, overflow: 'hidden', background: topColor, boxShadow: `0 0 ${16 + pulse * 30}px ${L.accent}${pulse ? 'CC' : '00'}, 0 16px 40px rgba(0,0,0,0.5)`}}>
      <div style={{position: 'absolute', bottom: 0, left: 0, width: '100%', height: BOARD * whiteFrac, background: bottomColor}} />
      <div style={{position: 'absolute', left: 0, width: '100%', textAlign: 'center', fontFamily: 'Inter', fontWeight: 800, fontSize: 15, letterSpacing: -0.5, color: bottomWinning ? topColor : bottomColor, ...(bottomWinning ? {bottom: 8} : {top: 8})}}>
        {label}
      </div>
    </div>
  );
};

const cameraAt = (d: LongData, f: number, flip: boolean) => {
  const xy = makeXY(BOARD, flip);
  // a slow breathing drift keeps the frame alive; zooms push in on the square of the action
  const idle = 1 + 0.006 * Math.sin(f / 140);
  for (const c of d.cams) {
    if (f >= c.from && f < c.to) {
      const env = Math.min(
        interpolate(f, [c.from, c.from + 14], [0, 1], {...clamp, easing: Easing.bezier(0.3, 0, 0.2, 1)}),
        interpolate(f, [c.to - 14, c.to], [1, 0], {...clamp, easing: Easing.bezier(0.6, 0, 0.7, 1)}),
      );
      const {cx, cy} = xy(c.sq);
      return {scale: idle * (1 + (c.peak - 1) * env), ox: cx, oy: cy, tx: (BOARD / 2 - cx) * 0.35 * env, ty: (BOARD / 2 - cy) * 0.35 * env};
    }
  }
  return {scale: idle, ox: BOARD / 2, oy: BOARD / 2, tx: 0, ty: 0};
};

const shakeAt = (d: LongData, f: number) => {
  let x = 0;
  let y = 0;
  for (const s of d.shakes) {
    if (f >= s.at && f < s.at + 30) {
      const k = s.amp * Math.exp(-(f - s.at) / 5);
      x += k * Math.sin(f * 2.3 + s.at);
      y += k * Math.cos(f * 3.1 + s.at);
    }
  }
  return {x, y};
};

const Pill: React.FC<{text: string; bg: string; color: string; s: number; size?: number}> = ({text, bg, color, s, size = 26}) => (
  <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: size, letterSpacing: 2, color, background: bg, borderRadius: 999, padding: '9px 24px', whiteSpace: 'nowrap', scale: String(interpolate(s, [0, 1], [0.7, 1])), opacity: interpolate(s, [0, 0.3], [0, 1], clamp)}}>{text}</div>
);

// ---------- full-screen moments ----------
const TitleSequence: React.FC<{d: LongData; f: number; fps: number}> = ({d, f, fps}) => {
  const t = d.titleSeq!;
  const L = lookOf(d);
  const inn = spring({frame: f - t.from, fps, config: {damping: 16, stiffness: 120}});
  const out = interpolate(f, [t.to - 10, t.to], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const top = d.meta.orientation === 'b' ? d.meta.white : d.meta.black;
  const bottom = d.meta.orientation === 'b' ? d.meta.black : d.meta.white;
  const side = (p: typeof top, dir: number, i: number) => {
    const s = spring({frame: f - t.from - 4 - i * 5, fps, config: {damping: 15, stiffness: 140}});
    return (
      <div style={{display: 'flex', alignItems: 'center', gap: 28, flexDirection: dir > 0 ? 'row' : 'row-reverse', translate: `${interpolate(s, [0, 1], [dir * -260, 0])}px 0px`, opacity: s}}>
        <div style={{width: 150, height: 150, borderRadius: 30, background: p.side === 'b' ? '#2A2F3A' : '#E9E9E9', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 20px 50px rgba(0,0,0,0.5)'}}>
          <Img src={staticFile(`pieces/${p.side}K.svg`)} style={{width: 120, height: 120}} />
        </div>
        <div style={{textAlign: dir > 0 ? 'left' : 'right'}}>
          <div style={{fontFamily: 'Anton', fontSize: 92, color: 'white', lineHeight: 1}}>{p.name}</div>
          <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 36, color: 'rgba(255,255,255,0.55)', marginTop: 6}}>{p.rating ?? ''}</div>
        </div>
      </div>
    );
  };
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 40%, ${L.bg[0]} 0%, ${L.bg[1]} 65%, ${L.bg[2]} 100%)`, clipPath: `inset(0 0 0 ${out * 100}%)`, opacity: interpolate(inn, [0, 0.2], [0, 1], clamp)}}>
      <AbsoluteFill style={{backgroundImage: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.025) 0 2px, transparent 2px 22px)'}} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', gap: 40}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 80}}>
          {side(bottom, 1, 0)}
          <div style={{fontFamily: 'Anton', fontSize: 70, color: L.accent, scale: String(spring({frame: f - t.from - 10, fps, config: {damping: 10, stiffness: 200}}))}}>VS</div>
          {side(top, -1, 1)}
        </div>
        <div style={{display: 'flex', gap: 20, marginTop: 30, opacity: spring({frame: f - t.from - 16, fps, config: {damping: 20}})}}>
          {d.meta.timeControl ? <Pill text={d.meta.timeControl.toUpperCase()} bg={L.accent} color="#000" s={1} /> : null}
          {d.meta.opening ? <Pill text={d.meta.opening.toUpperCase()} bg="rgba(255,255,255,0.12)" color="white" s={1} /> : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const ChapterCard: React.FC<{d: LongData; c: LongData['chapterCards'][number]; f: number; fps: number}> = ({d, c, f, fps}) => {
  const L = lookOf(d);
  const wipeIn = interpolate(f, [c.from, c.from + 9], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const wipeOut = interpolate(f, [c.to - 9, c.to], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const s = spring({frame: f - c.from - 5, fps, config: {damping: 15, stiffness: 150}});
  return (
    <AbsoluteFill style={{clipPath: `inset(0 ${(1 - wipeIn) * 100}% 0 ${wipeOut * 100}%)`, background: `linear-gradient(120deg, ${L.bg[0]} 0%, ${L.bg[2]} 100%)`}}>
      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 26, background: L.accent}} />
      <AbsoluteFill style={{justifyContent: 'center', paddingLeft: 180}}>
        <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 34, letterSpacing: 8, color: L.accent, opacity: s, translate: `${interpolate(s, [0, 1], [-60, 0])}px 0px`}}>CHAPTER {c.num}</div>
        <div style={{fontFamily: 'Anton', fontSize: 150, color: 'white', lineHeight: 1.05, marginTop: 10, opacity: s, translate: `${interpolate(s, [0, 1], [120, 0])}px 0px`}}>{c.title}</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------- the composition ----------
export const ChessLong: React.FC<{data: LongData | null}> = ({data}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (!data) return <AbsoluteFill style={{background: '#000'}} />;
  const d = data;
  const L = lookOf(d);
  const flip = d.meta.orientation === 'b';
  const view = boardAt(d, f);
  const board = d.boards[view.board];
  const cam = cameraAt(d, f, flip);
  const shake = shakeAt(d, f);
  const kingFall = d.kingFall === null ? 0 : interpolate(f, [d.kingFall, d.kingFall + 22], [0, 1], {...clamp, easing: Easing.bezier(0.5, 0, 0.9, 0.6)});
  const cold = d.coldOpen && inSpan(f, d.coldOpen) ? d.coldOpen : null;
  const variation = d.variations.find((v) => inSpan(f, v));
  const back = d.backs.find((b) => inSpan(f, b));
  const label = d.chapterLabels.find((c) => inSpan(f, c));
  const ff = (d.ffs || []).find((x) => inSpan(f, x));
  const end = d.endScreen && inSpan(f, d.endScreen) ? d.endScreen : null;
  const chapter = d.chapterCards.find((c) => inSpan(f, c));
  // whose move: after a white move it's black's turn (variation boards count from where they branched)
  let steps = 0;
  let k = view.board;
  while (d.boards[k].main === null && d.boards[k].prev !== null) {
    k = d.boards[k].prev!;
    steps++;
  }
  const blackToMove = ((d.boards[k].main ?? 0) + steps) % 2 === 1;
  const topSide = flip ? 'w' : 'b';
  const bottomSide = flip ? 'b' : 'w';

  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 35% 45%, ${L.bg[0]} 0%, ${L.bg[1]} 60%, ${L.bg[2]} 100%)`}}>
      <AbsoluteFill style={{backgroundImage: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.022) 0 2px, transparent 2px 22px)'}} />

      <AbsoluteFill style={{translate: `${shake.x}px ${shake.y}px`}}>
        {/* board in its camera window */}
        <div style={{position: 'absolute', left: BX - 14, top: BY - 14, width: BOARD + 28, height: BOARD + 28, overflow: 'hidden', borderRadius: 22, boxShadow: variation ? `0 0 0 5px ${L.accent}, 0 0 50px ${L.accent}55` : ff ? `0 0 0 5px ${L.accent}` : '0 30px 80px rgba(0,0,0,0.55)'}}>
          <div style={{position: 'absolute', left: 14, top: 14, width: BOARD, height: BOARD, scale: String(cam.scale), transformOrigin: `${cam.ox}px ${cam.oy}px`, translate: `${cam.tx}px ${cam.ty}px`}}>
            <LongBoard d={d} f={f} fps={fps} view={view} size={BOARD} kingFall={kingFall} variation={!!variation} />
          </div>
        </div>
        <EvalBar d={d} f={f} />

        {/* top line: chapter label, "what if", back to the game, fast-forward */}
        <div style={{position: 'absolute', left: BX - 64, top: 40, height: 52, display: 'flex', alignItems: 'center', gap: 16}}>
          {label && !cold ? <Pill text={label.title.toUpperCase()} bg="rgba(255,255,255,0.1)" color="white" s={spring({frame: f - label.from, fps, config: {damping: 16}})} size={24} /> : null}
          {variation ? <Pill text={`WHAT IF · ${variation.crumb}`} bg={L.accent} color="#000" s={spring({frame: f - variation.from, fps, config: {damping: 13, stiffness: 220}})} size={24} /> : null}
          {back && !variation ? <Pill text="BACK TO THE GAME" bg="#F2F2F2" color="#000" s={spring({frame: f - back.from, fps, config: {damping: 13, stiffness: 220}})} size={24} /> : null}
          {ff && !variation ? <Pill text={`FAST FORWARD · MOVE ${d.meta.moves[Math.min(d.meta.moves.length, Math.max(1, board.main ?? 1)) - 1].num}`} bg={L.accent} color="#000" s={spring({frame: f - ff.from, fps, config: {damping: 13, stiffness: 260}})} size={24} /> : null}
        </div>

        {/* right side: players and panel, or the cold-open headline */}
        {cold ? (
          (() => {
            const words = cold.text.split(' ');
            return (
              <div style={{position: 'absolute', left: PX, top: BY, width: PW, height: BOARD, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6}}>
                {words.map((w, i) => {
                  const s = spring({frame: f - 8 - i * 6, fps, config: {damping: 12, stiffness: 180, mass: 0.7}});
                  return (
                    <div key={i} style={{fontFamily: 'Anton', fontSize: words.length > 3 ? 128 : 150, lineHeight: 1.0, color: i % 2 === 1 ? L.accent : 'white', textShadow: '0 10px 0 rgba(0,0,0,0.45)', opacity: interpolate(s, [0, 0.3], [0, 1], clamp), translate: `${interpolate(s, [0, 1], [80, 0])}px 0px`}}>
                      {w}
                    </div>
                  );
                })}
              </div>
            );
          })()
        ) : end ? (
          (() => {
            const s = spring({frame: f - end.from, fps, config: {damping: 16, stiffness: 120}});
            return (
              <div style={{position: 'absolute', left: PX, top: BY, width: PW, height: BOARD, opacity: s}}>
                <div style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 26, letterSpacing: 6, color: L.accent}}>THANKS FOR WATCHING</div>
                <div style={{fontFamily: 'Anton', fontSize: 84, color: 'white', lineHeight: 1.05, marginTop: 10}}>WATCH NEXT</div>
              </div>
            );
          })()
        ) : (
          <>
            <PlayerCard d={d} side={topSide} board={board} x={PX} y={BY} w={PW} toMove={(topSide === 'b') === blackToMove} />
            <Panel d={d} f={f} fps={fps} board={view.board} x={PX} y={BY + 110} w={PW} h={BOARD - 220} />
            <PlayerCard d={d} side={bottomSide} board={board} x={PX} y={BY + BOARD - 92} w={PW} toMove={(bottomSide === 'b') === blackToMove} />
          </>
        )}

        {/* the finish */}
        {d.slam && inSpan(f, d.slam) && (
          <div style={{position: 'absolute', left: BX, top: BY, width: BOARD, height: BOARD, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            {(() => {
              const s = spring({frame: f - d.slam!.from, fps, config: {damping: 12, stiffness: 300, mass: 0.7}});
              return (
                <div style={{textAlign: 'center', scale: String(interpolate(s, [0, 1], [2.6, 1])), opacity: interpolate(s, [0, 0.3], [0, 1], clamp), rotate: '-6deg'}}>
                  <div style={{fontFamily: 'Anton', fontSize: 170, color: L.slam, WebkitTextStroke: '14px #000', paintOrder: 'stroke fill', textShadow: '0 12px 0 rgba(0,0,0,0.6)', lineHeight: 1}}>{d.slam!.title}</div>
                  {d.slam!.sub ? <div style={{fontFamily: 'Anton', fontSize: 70, color: 'white', WebkitTextStroke: '9px #000', paintOrder: 'stroke fill', marginTop: 6}}>{d.slam!.sub}</div> : null}
                </div>
              );
            })()}
          </div>
        )}
      </AbsoluteFill>

      {d.titleSeq && inSpan(f, d.titleSeq) && <TitleSequence d={d} f={f} fps={fps} />}
      {chapter && <ChapterCard d={d} c={chapter} f={f} fps={fps} />}

      {d.flashes.map((fl, i) => (f >= fl.at && f < fl.at + 10 ? <AbsoluteFill key={i} style={{background: fl.color, opacity: interpolate(f, [fl.at, fl.at + 10], [fl.strength, 0], clamp)}} /> : null))}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,0.45) 100%)', pointerEvents: 'none'}} />

      <Audio src={staticFile('long/voice.wav')} volume={1} />
      {d.events
        .filter((e) => e.dur && !e.ff)
        .map((e, i) => {
          const b = d.boards[e.board];
          const src = b.captured ? 'capture' : i % 2 ? 'move1' : 'move2';
          return <Audio key={'m' + i} from={e.at + e.dur - 2} src={staticFile(`sfx/${src}.wav`)} volume={b.captured ? 0.4 : 0.3} premountFor={fps} />;
        })}
      {d.sfx.map((s, i) => (
        <Audio key={'s' + i} from={s.at} src={staticFile(`sfx/${s.src}.wav`)} volume={s.vol} premountFor={fps} />
      ))}
    </AbsoluteFill>
  );
};

// ---------- thumbnail (1280x720 still) ----------
export const ChessThumb: React.FC<{data: LongData | null}> = ({data}) => {
  if (!data || !data.thumb) return <AbsoluteFill style={{background: '#000'}} />;
  const d = data;
  const L = lookOf(d);
  const th = d.thumb!;
  const size = 640;
  const xy = makeXY(size, d.meta.orientation === 'b');
  const words = th.text.toUpperCase().split(' ');
  const mid = Math.ceil(words.length / 2);
  const lines = words.length > 2 ? [words.slice(0, mid).join(' '), words.slice(mid).join(' ')] : words;
  const longest = Math.max(...lines.map((l) => l.length));
  const fs = Math.min(150, Math.floor(1150 / Math.max(4, longest)));
  const arrow = th.arrow;
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 30% 50%, ${L.bg[0]} 0%, ${L.bg[1]} 60%, ${L.bg[2]} 100%)`}}>
      <div style={{position: 'absolute', left: 36, top: 40, width: size, height: size, rotate: '-3deg', borderRadius: 18, overflow: 'hidden', boxShadow: '0 30px 70px rgba(0,0,0,0.7)', border: '6px solid rgba(255,255,255,0.9)'}}>
        <LongBoard d={{...d, arrows: [], badges: [], rings: [], highlights: [], motifs: []}} f={0} fps={30} view={{board: th.board, prev: null, t: 1, ff: false}} size={size} effects={false} />
        {arrow && (
          <svg width={size} height={size} style={{position: 'absolute', left: 0, top: 0}}>
            {(() => {
              const A = xy(arrow[0]);
              const B = xy(arrow[1]);
              const dx = B.cx - A.cx;
              const dy = B.cy - A.cy;
              const len = Math.hypot(dx, dy) || 1;
              const ux = dx / len;
              const uy = dy / len;
              const head = 54;
              const ex = B.cx - ux * 10;
              const ey = B.cy - uy * 10;
              const lx = ex - ux * head;
              const ly = ey - uy * head;
              return (
                <g>
                  <line x1={A.cx} y1={A.cy} x2={lx} y2={ly} stroke="#E5484D" strokeWidth={26} strokeLinecap="round" />
                  <polygon points={`${ex},${ey} ${lx - uy * 36},${ly + ux * 36} ${lx + uy * 36},${ly - ux * 36}`} fill="#E5484D" />
                </g>
              );
            })()}
          </svg>
        )}
      </div>
      <div style={{position: 'absolute', left: 720, right: 36, top: 0, bottom: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
        {lines.map((l, i) => (
          <div key={i} style={{fontFamily: 'Anton', fontSize: fs, lineHeight: 1.0, color: i === lines.length - 1 ? L.accent : 'white', WebkitTextStroke: '10px #000', paintOrder: 'stroke fill', textShadow: '0 10px 0 rgba(0,0,0,0.55)'}}>
            {l}
          </div>
        ))}
        {th.swing ? (
          <div style={{alignSelf: 'flex-start', marginTop: 26, fontFamily: 'Inter', fontWeight: 800, fontSize: 46, color: 'white', background: '#E5484D', borderRadius: 14, padding: '8px 22px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)', border: '4px solid white'}}>{th.swing}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
