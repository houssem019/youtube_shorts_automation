"""Narrator voice: Kokoro neural TTS, patched to report when every phoneme is spoken."""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

MODEL_URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
SR = 24000


def ensure_models(models_dir: Path, log=print) -> Path:
    """Download the voice model once and add the phoneme-duration output. Returns the patched model path."""
    models_dir.mkdir(parents=True, exist_ok=True)
    timed = models_dir / 'kokoro-timed.onnx'
    voices = models_dir / 'voices-v1.0.bin'
    base = models_dir / 'kokoro-v1.0.onnx'
    for f in (voices,) + (() if timed.exists() else (base,)):
        if not f.exists():
            log(f'Downloading voice model {f.name} (one time)...')
            urllib.request.urlretrieve(MODEL_URL + f.name, f)
    if not timed.exists():
        import onnx
        from onnx import TensorProto, helper
        log('Preparing the voice model for word timing (one time)...')
        m = onnx.load(str(base))
        m.graph.node.append(helper.make_node('Cast', ['/encoder/Clip_output_0'], ['duration'], to=TensorProto.INT64, name='dur_cast'))
        m.graph.output.append(helper.make_tensor_value_info('duration', TensorProto.INT64, None))
        onnx.save(m, str(timed))
        base.unlink(missing_ok=True)
    return timed


class Narrator:
    def __init__(self, models_dir: Path, voice: str = 'af_heart', log=print):
        from kokoro_onnx import Kokoro
        model = ensure_models(models_dir, log)
        self.k = Kokoro(str(model), str(models_dir / 'voices-v1.0.bin'))
        self.voice = voice

    def _word_groups(self, text: str, timings):
        groups, cur = [], []
        for t in timings:
            if t.phoneme == ' ':
                if cur:
                    groups.append(cur)
                    cur = []
            elif re.fullmatch(r'[.,!?;:—…\-"()]+', t.phoneme):
                continue
            else:
                cur.append(t)
        if cur:
            groups.append(cur)
        return groups

    def say(self, text: str, speed: float = 1.05):
        """Returns (audio float32 @24 kHz, [{t, s, e}] word timings in seconds)."""
        audio, sr, timings = self.k.create_timed(text, voice=self.voice, speed=speed, trim=True)
        words = text.split()
        groups = self._word_groups(text, timings)
        counts = []
        for w in words:
            ph = self.k.tokenizer.phonemize(w, 'en-us').strip()
            counts.append(max(1, len([x for x in ph.split(' ') if re.search(r'\w', x)])))
        out = []
        if timings and sum(counts) == len(groups):
            gi = 0
            for w, c in zip(words, counts):
                g = groups[gi:gi + c]
                gi += c
                out.append(dict(t=w, s=g[0][0].start, e=g[-1][-1].end))
        else:  # rare mismatch (odd tokens): spread words by length across the speech
            s0 = timings[0].start if timings else 0.0
            e0 = timings[-1].end if timings else len(audio) / sr
            total = sum(len(w) for w in words) or 1
            c = s0
            for w in words:
                d = (e0 - s0) * len(w) / total
                out.append(dict(t=w, s=c, e=c + d))
                c += d
        return audio, out
