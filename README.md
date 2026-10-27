# Chess Shorts

Turns chess.com games into edited, narrated YouTube videos and uploads them, one game per run, in two formats:
- **Shorts** (1080x1920, 45-50 s): a highlight built around the moment that decided the game.
- **Long videos** (1920x1080, 5-10 min): a full breakdown of the game for club players: the opening and its
  plans, the tactics, the missed ideas that would have won or saved it, and lessons at the end.

For each game it:
1. analyses every move with Stockfish (blunders, missed mates, the turning point, a "find the move" moment),
2. picks a storytelling style that fits the game (and wasn't used in the last few videos of that format),
3. has Claude write the narration in that style, then fact-check every sentence against the engine,
4. reads it with a neural narrator voice (Kokoro),
5. renders the video with Remotion (animated board, eval bar, arrows, badges, zooms, sound effects), mastered to
   YouTube loudness,
6. uploads it to YouTube as a private video, with a title written from the game's story (long videos also get
   a description with chapters and a generated thumbnail).

If the Shorts editor fails, it falls back to a simpler built-in render, so a run still produces a video. Long
videos have no fallback: if anything fails, nothing is uploaded.

## How it works

```
run_chess_automation.bat ─► main.py --format short|long [game]
                             ├─ src/chess_api.py       pick a game (chosen by you, else a random unedited one)
                             ├─ src/editor_bridge.py   run the video editor in its own Python environment
                             │    ├─ video_editor/make_short.py   Shorts
                             │    │    ├─ pipeline/analysis.py, story.py    Stockfish facts + the game's story
                             │    │    ├─ pipeline/styles.py                storytelling style + visual look
                             │    │    ├─ pipeline/writer_claude.py         commentary + title (built-in fallback:
                             │    │    │                                    writer_template.py)
                             │    │    ├─ pipeline/voice.py, timeline.py    narrator + word-timed edit timeline
                             │    │    └─ studio/ (Remotion) + render.py    draw, render, master audio
                             │    └─ video_editor/make_long.py    long videos
                             │         ├─ pipeline/analysis.py, story.py, styles.py, voice.py (shared)
                             │         ├─ pipeline/long/openings.py         opening name + where the book ends
                             │         ├─ pipeline/long/deep.py, motifs.py  top-3 engine moves at key moments,
                             │         │                                    rule-checked tactics, accuracy
                             │         ├─ pipeline/long/writer_long.py      outline + script + Stockfish-checked
                             │         │                                    variations + fact-check
                             │         ├─ pipeline/long/timeline_long.py    board states, cards, chapters
                             │         └─ studio/src/long/ (Remotion)       ChessLong video + ChessThumb thumbnail
                             ├─ src/video_gen.py       Shorts fallback: the original plain render
                             └─ src/youtube_api.py     upload (private), thumbnail
```

### Shorts: 45-50 second highlights
A Short doesn't replay the whole game. After the hook, the board rewinds straight to a few moves before the key
moment ("BACK TO MOVE 18"), quiet stretches after that fast-forward in under two seconds (a "MOVE N" counter and
a glow around the board), and the words go to the moment that decides the game. The voiced script is measured;
if it runs outside 45-50 s, Claude shortens or lengthens it and it is fact-checked again (up to two rounds).
The narrator alternates between a female and a male voice, one per uploaded Short.

### Long videos: 5-10 minute breakdowns
- **Structure:** a cold open on the key position, a title sequence, 3-6 chapters through the game (each with a
  chapter card), lessons, and an end screen. No subtitles, no music, one narrator (`am_michael`).
- **On screen:** the board and eval bar on the left; on the right, player cards with clocks and a panel that
  switches between the move list, cards (the opening and its ideas, the engine's top moves, a plan, accuracy,
  the lessons), "what if" lines and "pause and find the move" timers. An eval graph sits under the panel.
- **Suspense:** the eval graph and the move list only show the moves played so far, so nothing gives away what
  happens later.
- **Facts:** every "what if" line is played out and scored by Stockfish before the fact-check, and tactic names
  (fork, pin, skewer, ...) come from rule checks on the board.
- **Upload:** the title is Claude's story title (max 70 characters). The description has a summary, YouTube
  chapter timestamps, the opening, the game link and the hashtags. A thumbnail (the key position, a red arrow on
  the bad move, 2-4 big words, the eval swing) is set through the API; if YouTube refuses it (custom thumbnails
  need a phone-verified channel), the PNG is kept to upload by hand.
- **Time:** about 1-1.5 hours per video, mostly rendering.

### Storytelling styles
Each video uses one of ten styles. A style decides the angle of the story, the hook, the pacing, the closing
question, the title pattern and the look (colour palette, how a Short opens, the rewind transition, camera
strength). Long videos use the same styles with their own long-form briefs (`pipeline/long/briefs.py`).

| Style | Picked when | Short opening |
|---|---|---|
| The mate that got away | a forced mate was missed | headline |
| Race against the clock | a clock dropped under 20 s near the end, or the game was lost on time | headline |
| Winning, then not | the loser was ahead by 2+ pawns at some point | headline |
| Find the move | there's a clear "find the best move" moment | headline |
| The underdog | the player rated 100+ points lower won | headline |
| Total chaos | the lead changed hands 3+ times | replayed moves |
| Short and brutal | 20 moves or fewer | replayed moves |
| The long grind | 40+ moves, decided in the endgame | replayed moves |
| The one move | a single move decided it (the classic format) | replayed moves |
| How did we get here? | always possible | frozen board |

The best-fitting style that wasn't used in the last 3 uploads of that format wins. Headlines ("MISSED MATE",
"+4.3 AND LOST", "8 SECONDS LEFT") are built from the engine and clock facts, not written by the AI.

## Project layout

```
.
├── main.py                    entry point: pick game -> edit -> upload (--format short|long)
├── config.py                  all settings
├── run_chess_automation.bat   asks Short or Long, then an optional game link/ID
├── setup_editor.bat           one-time setup of the video editor
├── requirements.txt           packages for main.py
├── src/                       app code: chess.com, YouTube, editor bridge, plain renderer
├── video_editor/              the video pipeline (own Python 3.12 venv + Remotion project)
│   ├── make_short.py          CLI: PGN in, edited Short out
│   ├── make_long.py           CLI: PGN in, long video + thumbnail + upload details out
│   ├── pipeline/              analysis, story, styles, writers, voice, timeline, render; long/ for long videos
│   └── studio/                Remotion (React) project that draws the videos (src/long/ for long videos)
├── tests/                     manual check scripts (game pick, plain renderer, Stockfish)
├── scripts/                   helper scripts
├── assets/music/              background music for the plain render (not included)
└── data/                      runtime state and work files (not included)
```

## Requirements
- Windows 10/11 (the `.bat` files and venv paths are Windows-specific)
- Python 3.10+ for `main.py`, plus [uv](https://docs.astral.sh/uv/) (installed by `setup_editor.bat`) to create the
  editor's Python 3.12 environment (the Kokoro voice package doesn't support newer Pythons yet)
- [Node.js LTS](https://nodejs.org) for the Remotion renderer
- [Stockfish](https://stockfishchess.org/download/)
- A Google Cloud OAuth client for the YouTube Data API v3 (`client_secrets.json`)
- [Claude Code](https://claude.com/claude-code) logged in (`claude -p` is used), or an `ANTHROPIC_API_KEY`.
  Shorts fall back to a built-in writer without it; long videos need it.

## Setup
1. Install the main packages: `pip install -r requirements.txt`
2. Put your OAuth client file at `client_secrets.json` in the project root.
3. Set `CHESS_USERNAME` and `STOCKFISH_PATH` in `config.py` (or as environment variables).
4. Run `setup_editor.bat` once. It creates `video_editor\.venv`, installs the editor's packages and Remotion,
   downloads the narrator voice (~350 MB) and checks everything. It's safe to run again.
5. The first upload opens a browser window to sign in to YouTube; the token is saved in `data/token.json`. If the
   saved sign-in expires or is revoked, the browser opens again on the next upload.

## Usage
Double-click `run_chess_automation.bat`. It asks:
1. **Short or Long** (`1` / `2`; Enter = Short),
2. **a game**: paste a chess.com game link or ID, or press Enter for a random game without a video of that format:
   - Shorts: any of your games (up to 100 half-moves),
   - Long videos: a rapid game from the last 6 months, played at most 100 points below your best rating in that
     period (wider if all of those are done), 40-200 half-moves, not abandoned.

Shorts and long videos keep separate histories, so a game can get both. Both can also be passed as arguments:
`run_chess_automation.bat 185153537828 long` (a game given without a format makes a Short without asking).
A Short takes about 10-15 minutes, a long video about 1-1.5 hours. Videos are uploaded as private; publish them
by hand.

If a long run fails, the full editor output is in `data/temp/long/editor.log`. Running the same game again
reuses its analysis and script, so only the voice and the render are redone.

### Make a video without uploading
From the project root:
```
video_editor\.venv\Scripts\python video_editor\make_short.py --pgn game.pgn --out test.mp4 --username <you> --stockfish "<path to stockfish.exe>"
video_editor\.venv\Scripts\python video_editor\make_long.py --pgn game.pgn --out long.mp4 --work data\temp\long_test --username <you> --stockfish "<path to stockfish.exe>"
```
- `--style <id>` forces a style (`missed_mate`, `time_scramble`, `comeback`, `puzzle_challenge`, `underdog`, `chaos`,
  `miniature`, `long_grind`, `turning_point`, `how_did_we_get_here`)
- `--no-render` stops after building the timeline; preview it with `cd video_editor\studio` and `npx remotion studio`
  (composition `ChessShort` or `ChessLong`)
- `--script <script.json>` re-renders with a hand-edited script
- Shorts: `--writer template` skips Claude. Long: `--thumb-only` makes the timeline and the thumbnail only,
  `--resume` reuses the work folder's script for the same game.

`python -m tests.test_pick` checks the random game pick for both formats without making or uploading anything.

## Configuration (`config.py`)
| Setting | Meaning |
|---|---|
| `CHESS_USERNAME` | chess.com account whose games are used |
| `STOCKFISH_PATH` | path to the Stockfish executable |
| `EDITOR_ENABLED` | `False` uses the original plain render only (Shorts) |
| `EDITOR_VOICES` | Shorts narrators used in turn, one per uploaded Short (default `af_heart`, `am_michael`) |
| `EDITOR_WRITER` | Shorts: `auto` (Claude, else built-in), `claude` (Claude only), `template` (built-in only) |
| `EDITOR_TIMEOUT_MIN` | stop the Shorts editor after this many minutes and fall back |
| `LONG_VOICE` | long-video narrator (default `am_michael`) |
| `LONG_TIME_CLASS`, `LONG_MIN_PLIES`, `LONG_MAX_PLIES` | which games the random long pick may use |
| `LONG_RECENT_MONTHS`, `LONG_RATING_MARGIN` | random long picks: how many recent months, how far below your best rating |
| `LONG_TIMEOUT_MIN` | stop a long-video run after this many minutes |

Shorts titles are `<story title> #chess #chessgame #chesstactics` (`src/utils.py`); long videos carry the hashtags
in the description.

## Files created at runtime (git-ignored)
| Path | Contents |
|---|---|
| `data/history.json`, `data/history_long.json` | games already uploaded as a Short / as a long video |
| `data/editor_voice.json` | narrator of the last Short |
| `data/editor_style.json`, `data/editor_style_long.json` | styles and titles of recent uploads per format |
| `data/token.json` | YouTube sign-in token |
| `data/temp/` | the last Short's PGN, analysis, story, script and video |
| `data/temp/long/` | the last long video's work files: analysis, script, voice, thumbnail, `upload.json`, `editor.log`, video |
| `app.log` | log of every run |

## Known limitations
- Adding uploads to the "No Edits Just Chess" playlist fails: the YouTube sign-in only requests the upload
  permission. Adding the `https://www.googleapis.com/auth/youtube` scope in `config.py` and signing in again
  (delete `data/token.json`) would fix it.
- `tests/` holds manual scripts (`python -m tests.test_pick` from the project root), not an automated test suite.

## Credits
Chess logic: python-chess. Engine: Stockfish. Opening names: lichess-org/chess-openings (CC0). Narrator:
Kokoro-82M (Apache 2.0) via kokoro-onnx. Renderer: Remotion (free for individuals and small teams; see
remotion.dev/license). Pieces: cburnett set. Fonts: Anton and Inter (SIL OFL). Sound effects: Kenney (CC0) and
synthesised. No licence has been chosen for this project's own code yet.
