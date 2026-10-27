// Data the video is built from: the game (moves + engine evals) and the edit timeline
// generated from the commentary script (work/gen.py). Nothing here is hand-timed.
import game from './game.json';
import tl from './timeline.json';

export const FPS = 30;
export type Ply = (typeof game.plies)[number];
export const plies = game.plies as Ply[];
export const positions = game.positions as unknown as Record<string, string>[];

type Span = {from: number; to: number};
export type Timeline = {
  duration: number;
  beats: {ply: number; at: number; dur: number; ff?: boolean}[];
  statics: (Span & {ply: number; fallen: boolean})[];
  rewind: (Span & {fromPly: number; toPly?: number; label?: string; style?: 'tape' | 'flash' | 'clean'}) | null;
  ffs?: (Span & {fromPly: number; toPly: number})[]; // fast-forwarded runs of moves
  headline?: (Span & {text: string}) | null;
  look?: {bg: string[]; light: string; dark: string; accent: string; slam: string} | null;
  arrows: (Span & {a: string; b: string; color: string; dashed: boolean})[];
  badges: (Span & {sq: string; text: string; color: string})[];
  cams: (Span & {sq: string; peak: number})[];
  shakes: {at: number; amp: number}[];
  flashes: {at: number; color: string; strength: number}[];
  sfx: {at: number; src: string; vol: number}[];
  rings: (Span & {sq: string; color: string})[];
  slam: (Span & {title: string; sub: string}) | null;
  countdown: (Span & {title: string; sub: string}) | null;
  kingFall: number | null;
  evalPulse: Span[];
  evalSlow: number[];
  captions: (Span & {words: {t: string; f: number}[]})[];
  meta: {
    orientation: 'w' | 'b';
    white: {name: string; rating: number | null; side: 'w'};
    black: {name: string; rating: number | null; side: 'b'};
    badPlies: number[];
    lastPly: number;
    fallenKing: 'w' | 'b' | null;
  };
};
export const T = tl as unknown as Timeline;
// colours of this video's look (the original palette when the timeline has none)
export const LOOK = {bg: ['#1B2333', '#0C1018', '#06080C'], light: '#E6E1D3', dark: '#5E7C8A', accent: '#FFD43B', slam: '#FF4D4F', ...(T.look || {})};
export const inSpan = (f: number, s: Span) => f >= s.from && f < s.to;
