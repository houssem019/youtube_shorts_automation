import React from 'react';
import {Composition} from 'remotion';
import {ChessShort} from './ChessShort';
import {FPS, T} from './story';
import {ChessLong, ChessThumb} from './long/ChessLong';
import {loadLongData, LongData} from './long/data';

// The long video reads its data from public/long/props.json (written by make_long.py) when it is rendered.
// (no long video made yet on this machine: the compositions stay empty instead of breaking the Studio)
const tryLoad = () => loadLongData().catch(() => null);
const longMeta = async () => {
  const data = await tryLoad();
  return {durationInFrames: Math.max(1, data?.duration ?? 1), props: {data}};
};
const thumbMeta = async () => ({durationInFrames: 1, props: {data: await tryLoad()}});

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="ChessShort" component={ChessShort} durationInFrames={T.duration} fps={FPS} width={1080} height={1920} />
    <Composition id="ChessLong" component={ChessLong} defaultProps={{data: null as LongData | null}} calculateMetadata={longMeta} durationInFrames={1} fps={FPS} width={1920} height={1080} />
    <Composition id="ChessThumb" component={ChessThumb} defaultProps={{data: null as LongData | null}} calculateMetadata={thumbMeta} durationInFrames={1} fps={FPS} width={1280} height={720} />
  </>
);
