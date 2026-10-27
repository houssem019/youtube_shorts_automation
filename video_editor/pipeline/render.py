"""Render the Remotion video and master the audio for YouTube."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return 'ffmpeg'


def duration_s(path: Path) -> float | None:
    """Length of a video file in seconds (None if ffmpeg can't read it)."""
    r = subprocess.run([ffmpeg_exe(), '-i', str(path)], capture_output=True, text=True, errors='replace')
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


def render(studio: Path, out_mp4: Path, log=print, composition: str = 'ChessShort', expect_s: float | None = None) -> None:
    """expect_s: the video's length; when given, a complete file counts even if Remotion exits with an error code
    (on Windows npx/Remotion can exit with -1 after the file is finished)."""
    raw = studio / 'out' / f'render_{composition}.mp4' if composition != 'ChessShort' else studio / 'out' / 'render.mp4'
    raw.parent.mkdir(exist_ok=True)
    if expect_s:
        raw.unlink(missing_ok=True)  # an old file must not pass for this render
    cmd = ['npx', 'remotion', 'render', 'src/index.ts', composition, str(raw), '--codec=h264', '--crf=18', '--log=warn']
    if os.environ.get('REMOTION_BROWSER'):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    if os.environ.get('REMOTION_CONCURRENCY'):
        cmd.append(f"--concurrency={os.environ['REMOTION_CONCURRENCY']}")
    log('Rendering the video (this takes a few minutes)...' if composition == 'ChessShort' else
        'Rendering the video (a long video takes 1-2 hours)...')
    if expect_s:
        # own process group: Remotion's browser cleanup can't take this process down with it
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        r = subprocess.run(cmd, cwd=studio, shell=sys.platform == 'win32', creationflags=flags)
        got = duration_s(raw) if raw.exists() else None
        if r.returncode != 0 and got is not None and abs(got - expect_s) < 2:
            log(f'Remotion exited with code {r.returncode}, but the video is complete ({got:.0f} s); continuing.')
        elif r.returncode != 0 or got is None:
            raise RuntimeError(f'Remotion render failed (exit code {r.returncode})')
    else:
        r = subprocess.run(cmd, cwd=studio, shell=sys.platform == 'win32')
        if r.returncode != 0 or not raw.exists():
            raise RuntimeError('Remotion render failed')
    log('Mastering audio to YouTube loudness...')
    r = subprocess.run([ffmpeg_exe(), '-v', 'error', '-y', '-i', str(raw), '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=9',
                        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', str(out_mp4)])
    if r.returncode != 0:
        raise RuntimeError('ffmpeg loudness step failed')


def master_voice(raw_wav: Path, out_wav: Path) -> None:
    """Light cleanup so the narrator sounds like a mic in a room rather than a dry synthetic file."""
    chain = ('highpass=f=75,equalizer=f=220:t=q:w=1.2:g=-2,equalizer=f=3200:t=q:w=1.5:g=2.5,'
             'acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,aecho=0.85:0.5:28|47:0.10|0.06,'
             'loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000')
    r = subprocess.run([ffmpeg_exe(), '-v', 'error', '-y', '-i', str(raw_wav), '-af', chain, '-ac', '2', str(out_wav)])
    if r.returncode != 0:
        raise RuntimeError('ffmpeg voice mastering failed')


def still(studio: Path, composition: str, out_png: Path, frame: int = 0) -> None:
    """One frame as an image (the long video's thumbnail)."""
    cmd = ['npx', 'remotion', 'still', 'src/index.ts', composition, str(out_png), f'--frame={frame}', '--image-format=png', '--log=warn']
    if os.environ.get('REMOTION_BROWSER'):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    r = subprocess.run(cmd, cwd=studio, shell=sys.platform == 'win32')
    if r.returncode != 0 or not out_png.exists():
        raise RuntimeError('Remotion still failed')
