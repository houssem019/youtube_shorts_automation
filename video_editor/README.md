# Video editor

Makes one edited, narrated chess Short from a PGN. `main.py` runs it through `src/editor_bridge.py`;
it can also be run on its own (see "Commands"). Setup: `setup_editor.bat` in the project root.

## Pipeline
| Step | File | What it does |
|---|---|---|
| Analysis | `pipeline/analysis.py` | Stockfish eval, best move and quality (win%-based blunder/mistake labels) for every ply; clocks |
| Story | `pipeline/story.py` | winner, how it ended, turning point, key moments, the loser's best moment, a "find the move" puzzle |
| Style | `pipeline/styles.py` | picks the storytelling style and its look (see below) |
| Writer | `pipeline/writer_claude.py` | Claude writes the commentary script + title, it's validated (`script_schema.py`), then a second Claude pass fact-checks every sentence. Fallback: `writer_template.py` (plain, always valid) |
| Voice | `pipeline/voice.py` | Kokoro narrator; the ONNX model is patched once to output phoneme durations, so every word has an exact timestamp |
| Timeline | `pipeline/timeline.py` | voices each line, lands moves on the spoken word, captions, effects, sound effects, hook / rewind / puzzle countdown / slam, automatic `??` badges |
| Render | `studio/` + `pipeline/render.py` | Remotion draws and renders the video; ffmpeg masters the audio to -14 LUFS |

Work files for a game (`game.pgn`, `analysis.json`, `story.json`, `script.json`, `voice_raw.wav`) go to the
`--work` folder (`data/temp/edit/` when run by `main.py`).

## Styles and looks
`pipeline/styles.py` holds the style map. Each style has:
- `fits(a, s)`: returns the facts that make the style fit the game, or `None`;
- `score`: how strongly it wins when it fits (rarer stories score higher);
- `brief`: writing directions for Claude (angle, hook, pacing, outro, title pattern);
- an entry in `LOOK`: palette, opener (`still` / `replay` / `headline`), transition (`tape` / `flash` / `clean`),
  camera `zoom`, and a headline built from the facts.

`choose()` takes the highest-scoring fitting style not used in the last 3 uploads (`--recent` file). The style's
facts are given to both the writer and the fact-checker. The built-in writer, and timelines without a look, use
the original look (midnight palette, frozen board, tape rewind). To add a style: write a `fits` function, add an
entry to `STYLES` and to `LOOK`.

## Commands
From the project root:
```
video_editor\.venv\Scripts\python video_editor\make_short.py --pgn game.pgn --out my.mp4 --username <you> --stockfish "<stockfish.exe>"
```
| Option | Meaning |
|---|---|
| `--voice af_heart` | Kokoro voice (e.g. `am_michael`, `am_fenrir`, `bm_george`) |
| `--writer auto\|claude\|template` | who writes the commentary |
| `--style <id>` | force a style |
| `--recent data\editor_style.json` | avoid the styles and titles of recent uploads (read only) |
| `--script path\to\script.json` | use a hand-edited script instead of writing one |
| `--no-render` | stop after the timeline; preview with `cd video_editor\studio` then `npx remotion studio` |
| `--work <folder>` | where the work files go |
| `--depth 16` | Stockfish depth |

`setup_check.py` re-checks Stockfish, the voices and the Claude CLI.

## Script format
See the docstring in `pipeline/script_schema.py`: `title`, `hook` (lines over a still board, the last one plays
the rewind), `body` (starts at any ply, the rewind goes back to it; from there every ply exactly once, as `moves`
anchored to spoken words, `spread` over a line, or `skip` = fast-forward in under 2 s),
`outro`, and effects (`arrow`, `badge`, `ring`, `zoom`, `evalbar`, `slam`) anchored to words.
`pipeline/example_script.json` is the hand-written example given to Claude.

## Long videos (`make_long.py`)
A 16:9, 5-10 minute breakdown of one game (`main.py --format long`). Same analysis, story, styles and voice as
the Shorts, plus:

| Step | File | What it does |
|---|---|---|
| Opening | `pipeline/long/openings.py` | opening name + ECO from the Lichess opening tables (`pipeline/long/openings/*.tsv`, CC0) and the ply where the game leaves the named lines |
| Deep look | `pipeline/long/deep.py` | MultiPV-3 (depth 18) at every mistake/blunder and the turning point, the best reply to each, accuracy and error counts, checks "what if" lines |
| Tactics | `pipeline/long/motifs.py` | rule-checked facts: fork, pin, skewer, discovered attack/check, mate threat, hanging piece, material won by a line |
| Writer | `pipeline/long/writer_long.py` | Claude outlines then writes the script (`pipeline/long/schema_long.py`); every variation is played and scored by Stockfish and given to the fact-check pass; a fit pass keeps it at 5.5-9 min |
| Timeline | `pipeline/long/timeline_long.py` | board states (game + variation positions) and events, chapter cards, panel cards, think pauses, effects, YouTube chapter times; writes `studio/public/long/props.json` and `voice.wav` |
| Render | `studio/src/long/` | `ChessLong` (1920x1080): board + eval bar, side panel (players, clocks, move list, opening / plan / candidates / lesson / stats cards, eval graph, "what if" line, think timer), cold open, title sequence, chapter cards, end screen. `ChessThumb` (1280x720): the thumbnail |

No captions and no music in long videos. Narrator: `am_michael`. Outputs in `--work`: `script.json`,
`thumbnail.png`, `upload.json` (title, summary, chapters, opening, thumbnail path for the uploader).
Options: `--no-render`, `--thumb-only`, `--script <json>`, `--resume` (reuse the work folder's script for the same game), `--style <id>`, `--recent <json>`, `--voice`, `--depth`. A failed run's full output is in `<work>/editor.log`.

## Credits / licences
Sound effects: Kenney (kenney.nl), CC0, plus a few synthesised. Pieces: cburnett set (as bundled with
python-chess). Opening names: lichess-org/chess-openings (CC0). Fonts: Anton and Inter (SIL OFL). Voice: Kokoro-82M (Apache 2.0). Renderer: Remotion
(free for individuals and small teams; check remotion.dev/license if the channel grows into a company).
