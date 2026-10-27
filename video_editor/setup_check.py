"""Run by setup_editor.bat: downloads the voice model and checks every part of the editor."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
ok = True


def step(name, fn):
    global ok
    try:
        msg = fn()
        print(f'  [OK]   {name}{": " + msg if msg else ""}')
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f'  [FAIL] {name}: {e}')


def stockfish():
    import chess.engine
    from config import STOCKFISH_PATH
    e = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    e.quit()
    return STOCKFISH_PATH


def voice():
    from config import EDITOR_VOICES
    from pipeline.voice import Narrator
    n = Narrator(HERE / 'models')
    for v in EDITOR_VOICES:
        n.voice = v
        audio, words = n.say('Queen takes h7, checkmate.')
        assert len(words) == 4 and len(audio) > 0, f'word timing did not work for {v}'
    return f'{", ".join(EDITOR_VOICES)}, word timing OK'


def writer():
    if os.environ.get('ANTHROPIC_API_KEY'):
        return 'Claude via ANTHROPIC_API_KEY'
    exe = shutil.which('claude') or shutil.which('claude.cmd')
    if not exe:
        return ('Claude Code not found, so the built-in commentary writer will be used. For Claude-written commentary, '
                'install Claude Code (npm install -g @anthropic-ai/claude-code), run "claude" once to log in, then run this setup again.')
    r = subprocess.run([exe, '-p', '--output-format', 'text'], input='Reply with exactly: OK', capture_output=True, text=True, timeout=180,
                       cwd=tempfile.gettempdir())
    if 'OK' not in r.stdout:
        return f'Claude Code is installed but did not answer (log in by running "claude" once). Built-in writer will be used meanwhile. {r.stderr[-200:]}'
    return 'Claude Code CLI is logged in; Claude will write the commentary'


print('Checking the video editor...')
step('Stockfish', stockfish)
step('Narrator voices (downloads ~350 MB the first time)', voice)
step('Commentary writer', writer)
print('All good. Run run_chess_automation.bat as usual.' if ok else 'Some checks failed; fix the items above and run setup_editor.bat again.')
sys.exit(0 if ok else 1)
