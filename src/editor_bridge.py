"""Runs the video editor (video_editor/make_short.py) in its own Python environment."""
import json
import logging
import os
import subprocess

from config import (CHESS_USERNAME, EDITOR_DIR, EDITOR_PYTHON, EDITOR_STYLE_FILE, EDITOR_TIMEOUT_MIN, EDITOR_VOICE_FILE,
                    EDITOR_VOICES, EDITOR_WRITER, LONG_STYLE_FILE, LONG_TIMEOUT_MIN, LONG_VOICE, LONG_WORK_DIR,
                    STOCKFISH_PATH, TEMP_DIR)

logger = logging.getLogger(__name__)
WORK_DIR = os.path.join(TEMP_DIR, "edit")


def next_voice():
    """The narrator after the one used in the last uploaded video (voices take turns)."""
    last = None
    try:
        with open(EDITOR_VOICE_FILE, encoding="utf-8") as f:
            last = json.load(f).get("last")
    except Exception:
        pass
    if last not in EDITOR_VOICES:
        return EDITOR_VOICES[0]
    return EDITOR_VOICES[(EDITOR_VOICES.index(last) + 1) % len(EDITOR_VOICES)]


def remember_voice(voice):
    """Call after a successful upload, so the next video uses the other voice."""
    try:
        with open(EDITOR_VOICE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last": voice}, f)
    except Exception as e:
        logger.error(f"Could not save the narrator voice: {e}")


def remember_style(style, title, path=EDITOR_STYLE_FILE):
    """Call after a successful upload: the editor avoids recently used styles and title patterns."""
    if not style:
        return  # nothing to avoid next time (the script couldn't be read back)
    try:
        recent = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                recent = json.load(f).get("recent", [])
        recent = (recent + [{"style": style, "title": title}])[-20:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"recent": recent}, f, indent=1)
    except Exception as e:
        logger.error(f"Could not save the video style: {e}")


def _ready():
    if not os.path.exists(EDITOR_PYTHON):
        logger.warning("Video editor is not set up yet (run setup_editor.bat once).")
        return False
    if not os.path.exists(STOCKFISH_PATH):
        logger.warning(f"Stockfish not found at {STOCKFISH_PATH} (set STOCKFISH_PATH in config.py).")
        return False
    return True


def _write_pgn(pgn, out_path, *stale):
    """Writes the game for the editor and removes outputs of an earlier run. Returns the PGN path."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    pgn_path = os.path.join(TEMP_DIR, "game.pgn")
    with open(pgn_path, "w", encoding="utf-8") as f:
        f.write(pgn)
    for path in (out_path,) + stale:
        if os.path.exists(path):
            os.remove(path)
    return pgn_path


def _run_editor(cmd, out_path, timeout_min, log_path=None):
    """Runs an editor command, logging its [editor] lines (everything goes to log_path). True when it made out_path."""
    full = open(log_path, "w", encoding="utf-8") if log_path else None
    try:
        proc = subprocess.Popen(cmd, cwd=EDITOR_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            line = line.rstrip()
            if full:
                full.write(line + "\n")
                full.flush()
            if line.startswith("[editor]"):
                logger.info(line)
            elif line and not line.startswith(("Rendered", "Encoded", "Bundling")):
                logger.debug(line)
        proc.wait(timeout=timeout_min * 60)
    except Exception as e:
        logger.error(f"Video editor crashed: {e}")
        return False
    finally:
        if full:
            full.close()
    if proc.returncode != 0 or not os.path.exists(out_path):
        where = f"the full editor output is in {log_path}" if log_path else "see app.log"
        logger.error(f"Video editor failed (exit code {proc.returncode}); {where}.")
        return False
    return True


def make_edited_short(pgn: str, out_path: str):
    """Returns {"path", "title", "voice", "style"} for the edited video, or None if the editor isn't set up or fails.
    "title" is the story title the commentary writer gave the video (None if it gave none)."""
    if not _ready():
        return None
    script_path = os.path.join(WORK_DIR, "script.json")
    pgn_path = _write_pgn(pgn, out_path, script_path)

    voice = next_voice()
    logger.info(f"Narrator: {voice}")
    cmd = [EDITOR_PYTHON, os.path.join(EDITOR_DIR, "make_short.py"),
           "--pgn", pgn_path, "--out", out_path, "--username", CHESS_USERNAME,
           "--stockfish", STOCKFISH_PATH, "--voice", voice, "--writer", EDITOR_WRITER,
           "--work", WORK_DIR, "--recent", EDITOR_STYLE_FILE]
    if not _run_editor(cmd, out_path, EDITOR_TIMEOUT_MIN):
        return None

    script = {}
    try:
        with open(script_path, encoding="utf-8") as f:
            script = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read the story title: {e}")
    return {"path": out_path, "title": script.get("title"), "voice": voice, "style": script.get("style")}


def make_long_video(pgn: str, out_path: str):
    """Runs video_editor/make_long.py. Returns {"path", "title", "summary", "chapters", "opening", "thumbnail",
    "style"} (from the editor's upload.json), or None if the editor isn't set up or fails."""
    if not _ready():
        return None
    meta_path = os.path.join(LONG_WORK_DIR, "upload.json")
    pgn_path = _write_pgn(pgn, out_path, meta_path)
    logger.info(f"Narrator: {LONG_VOICE}")
    cmd = [EDITOR_PYTHON, os.path.join(EDITOR_DIR, "make_long.py"),
           "--pgn", pgn_path, "--out", out_path, "--username", CHESS_USERNAME,
           "--stockfish", STOCKFISH_PATH, "--voice", LONG_VOICE,
           "--work", LONG_WORK_DIR, "--recent", LONG_STYLE_FILE, "--resume"]
    if not _run_editor(cmd, out_path, LONG_TIMEOUT_MIN, os.path.join(LONG_WORK_DIR, "editor.log")):
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read the video details: {e}")
        meta = {}
    return {**meta, "path": out_path}
