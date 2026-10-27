// Data for the long video (written by pipeline/long/timeline_long.py to public/long/props.json).
// Everything is in frames at 30 fps. Nothing here is hand-timed.
import {continueRender, delayRender, Easing, interpolate, staticFile} from 'remotion';

export const FPS = 30;
type Span = {from: number; to: number};

export type BoardData = {
  pos: Record<string, string>;
  last: [string, string] | null;
  check: string | null;
  mate: boolean;
  cp: number;
  mateIn: number | null;
  label: string;
  cls: string | null;
  main: number | null; // game ply, or null for a variation position
  prev: number | null;
  anim: [string, string][] | null;
  captured: string | null;
  clocks: {w: number | null; b: number | null};
};
export type Card = Span & {
  type: 'opening' | 'ideas' | 'candidates' | 'lesson' | 'stats' | 'graph';
  name?: string;
  eco?: string | null;
  ideas?: string[];
  heading?: string;
  points?: string[];
  title?: string;
  move?: string;
  items?: {san: string; ev: string; cp: number; mate: number | null}[];
  played?: string;
  num?: number;
  text?: string;
  sides?: Record<'w' | 'b', {accuracy: number; blunders: number; mistakes: number; inaccuracies: number}>;
};
export type Player = {name: string; rating: number | null; side: 'w' | 'b'};
export type LongData = {
  duration: number;
  boards: BoardData[];
  events: {at: number; board: number; dur: number; ff?: boolean}[];
  ffs?: (Span & {fromPly: number; toPly: number})[];
  arrows: (Span & {a: string; b: string; color: string; dashed: boolean})[];
  badges: (Span & {sq: string; text: string; color: string})[];
  rings: (Span & {sq: string; color: string})[];
  highlights: (Span & {squares: string[]; color: string})[];
  motifs: (Span & {name: string; sq: string; targets: string[]})[];
  cams: (Span & {sq: string; peak: number})[];
  shakes: {at: number; amp: number}[];
  flashes: {at: number; color: string; strength: number}[];
  sfx: {at: number; src: string; vol: number}[];
  cards: Card[];
  thinks: (Span & {title: string; sub: string})[];
  variations: (Span & {crumb: string; boards: number[]})[];
  backs: Span[];
  chapterCards: (Span & {num: number; title: string})[];
  chapterLabels: (Span & {title: string})[];
  evalPulse: Span[];
  evalSlow: number[];
  slam: (Span & {title: string; sub: string}) | null;
  kingFall: number | null;
  coldOpen: (Span & {text: string}) | null;
  titleSeq: Span | null;
  endScreen: Span | null;
  look: {bg: string[]; light: string; dark: string; accent: string; slam: string} | null;
  meta: {
    orientation: 'w' | 'b';
    white: Player;
    black: Player;
    timeControl: string;
    opening: string;
    moves: {ply: number; num: number; color: 'w' | 'b'; san: string; cls: string}[];
    curve: number[];
    swings: number[];
    lastPly: number;
    fallenKing: 'w' | 'b' | null;
  };
  thumb?: {board: number; text: string; arrow: [string, string] | null; swing: string | null};
};

export const DEFAULT_LOOK = {bg: ['#1B2333', '#0C1018', '#06080C'], light: '#E6E1D3', dark: '#5E7C8A', accent: '#FFD43B', slam: '#FF4D4F'};
export const lookOf = (d: LongData) => ({...DEFAULT_LOOK, ...(d.look || {})});
export const inSpan = (f: number, s: Span) => f >= s.from && f < s.to;
export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ---------- the board on screen at frame f ----------
export type BoardView = {board: number; prev: number | null; t: number; ff: boolean};
export const boardAt = (d: LongData, f: number): BoardView => {
  let cur = null as null | LongData['events'][number];
  for (const e of d.events) {
    if (e.at <= f) cur = e;
    else break;
  }
  if (!cur) return {board: d.events.length ? d.events[0].board : 0, prev: null, t: 1, ff: false};
  if (!cur.dur || f >= cur.at + cur.dur) return {board: cur.board, prev: null, t: 1, ff: !!cur.ff};
  const p = (f - cur.at) / cur.dur;
  return {board: cur.board, prev: d.boards[cur.board].prev, t: Easing.bezier(0.33, 0, 0.15, 1)(Math.max(0, p)), ff: !!cur.ff};
};

// the game ply the viewer is "at" (a variation counts as the position it branched from)
export const mainPlyOf = (d: LongData, b: number): number => {
  let k = b;
  while (d.boards[k].main === null && d.boards[k].prev !== null) k = d.boards[k].prev!;
  return d.boards[k].main ?? 0;
};

// ---------- evaluation ----------
export const toFrac = (cp: number) => 0.5 + 0.5 * Math.tanh(cp / 450);
export const evalOf = (b: BoardData): {frac: number; label: string} => {
  if (b.mate) return {frac: b.cp > 0 ? 1 : 0, label: b.cp > 0 ? '1-0' : '0-1'};
  if (b.mateIn !== null && b.mateIn !== undefined && b.mateIn !== 0) return {frac: b.mateIn > 0 ? 1 : 0, label: `M${Math.abs(b.mateIn)}`};
  return {frac: toFrac(b.cp), label: `${b.cp > 0 ? '+' : ''}${(b.cp / 100).toFixed(1)}`};
};
export const evalAt = (d: LongData, f: number): {frac: number; label: string} => {
  const v = boardAt(d, f);
  const now = evalOf(d.boards[v.board]);
  // the bar moves after the piece lands (slowly after a blunder)
  let cur = null as null | LongData['events'][number];
  for (const e of d.events) if (e.at + e.dur <= f) cur = e;
  if (!cur || !cur.dur) return now;
  const b = d.boards[cur.board];
  const slow = b.main !== null && d.evalSlow.includes(b.main);
  const t = interpolate(f, [cur.at + cur.dur, cur.at + cur.dur + (slow ? 26 : 10)], [0, 1], {...clamp, easing: Easing.bezier(0.7, 0, 0.2, 1)});
  const before = b.prev !== null ? evalOf(d.boards[b.prev]) : now;
  if (cur.board !== v.board) return now;
  return {frac: before.frac + (now.frac - before.frac) * t, label: now.label};
};

export const fmtClock = (s: number | null) => (s === null || s === undefined ? '' : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`);

// ---------- fonts ----------
let fontsRequested = false;
export const loadFonts = () => {
  if (fontsRequested) return;
  fontsRequested = true;
  const handle = delayRender('Loading fonts');
  const faces = [
    new FontFace('Anton', `url(${staticFile('fonts/Anton.woff2')})`),
    new FontFace('Inter', `url(${staticFile('fonts/Inter800.woff2')})`, {weight: '800'}),
    new FontFace('Inter', `url(${staticFile('fonts/Inter600.woff2')})`, {weight: '600'}),
  ];
  Promise.all(faces.map((x) => x.load()))
    .then((loaded) => {
      loaded.forEach((x) => (document.fonts as unknown as {add: (y: FontFace) => void}).add(x));
      continueRender(handle);
    })
    .catch(() => continueRender(handle));
};

export const loadLongData = async (): Promise<LongData> => {
  const r = await fetch(staticFile('long/props.json'));
  return (await r.json()) as LongData;
};
