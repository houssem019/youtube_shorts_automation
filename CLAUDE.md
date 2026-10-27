# Chess Shorts automation — context for Claude Code

This project turns my chess.com games into YouTube videos and uploads them: Shorts and (since 2026-10-21)
long-form breakdowns. `run_chess_automation.bat` asks Short or Long, then the game, and runs `main.py`, which
makes one edited, narrated video per run (`video_editor/`) and uploads it.
The public-facing overview is `README.md`; editor internals are in `video_editor/README.md`.
Read this before changing anything.

## What I want (owner's preferences)
- Videos should feel professionally edited, exciting and easy to follow, NOT AI-generated. People dislike AI slop.
- Real commentary on the game (ideas, mistakes, threats), not just reading moves. No meme announcer clips,
  no cliché punchlines, no AI-sounding phrases.
- I don't use my own voice: a narrator voice (Kokoro TTS) reads the commentary. Videos alternate between a
  female (`af_heart`) and a male (`am_michael`) narrator, one per uploaded video (`EDITOR_VOICES`).
- No background music in the edited videos.
- YouTube title = a short story title for that game (written with the commentary, max 40 chars) followed by the
  fixed hashtags `#chess #chessgame #chesstactics`. Keep those hashtags exactly as they are
  (`src/utils.py:HASHTAGS`). #gothamchess and #magnuscarlsen were removed on 2026-10-19 (misleading). The plain-render fallback uses "Chess Game" + the same hashtags.
- Uploads stay private (I publish by hand). I manage the "No Edits Just Chess" playlist myself.
- Animations, eval bar, arrows, badges, zooms and sound effects in the current style are liked; keep them.
- Videos must not feel repetitive: each one uses a storytelling style from `video_editor/pipeline/styles.py`
  (missed mate, time scramble, comeback, find-the-move, underdog, chaos, miniature, long grind, turning point,
  how-did-we-get-here). The best-fitting style not used in the last 3 uploads is picked; Claude is also shown the
  recent titles so titles don't repeat a pattern. A style sets the writing (hook, angle, pacing, effects emphasis,
  outro, title) AND the look (`LOOK` in styles.py): colour palette (6), hook opening (frozen board / replayed
  moves / big headline from the game facts), rewind transition (tape / flash / "BACK TO MOVE N") and camera
  strength. The animations, eval bar, arrows, badges, captions and sounds are the same parts in every look.
  The built-in writer and old timelines use the original look (midnight colours, frozen board, tape rewind).
  Only words were varied at first and I still saw "the same video": visible variety matters.
- I can choose the game: the bat asks for the format (Short / Long), then a chess.com link/ID; Enter = a random
  game that has no video of that format yet (`get_random_unedited_game`). The "newest game" pick was removed on
  2026-10-21 (my latest game is often a bad loss). Shorts and long videos have separate histories
  (`history.json` / `history_long.json`), so one game can get both.
- Shorts are finished: don't keep reworking them. The focus is long-form videos (see below).
- Length: 45-50 s highlights (since 2026-10-19; ~90 s full-game replays were too long, viewers skipped). Don't make
  it shorter by talking faster: the first edit was "too fast and hard to follow". The rewind goes straight to a
  few moves before the key moment, quiet stretches use "skip" (fast-forward), and `make_short.py` has Claude
  shorten/lengthen a voiced script that runs outside 45-50 s (`writer_claude.fit`, then fact-checked again).
- Don't change working parts I didn't ask about; push back if a change risks the quality or stability of the videos.

## Long-form videos (owner's preferences, 2026-10-21)
- Goal: monetization. 16:9, 5-10 minutes (target ~6-8). Fun to watch AND instructive for club players (I'm ~1650
  rapid): explain the opening and its plans, the ideas behind moves, the tactics, and the missed ideas that would
  have won or saved the game. Lessons at the end.
- Professionally edited with animations and motion graphics; clear voice; NO subtitles; NO music.
- Narrator: always `am_michael` (`LONG_VOICE`), no alternation.
- Random long pick: recent games played at a good rating (`get_recent_good_game`: last 6 months, at most 100
  points below my best rating in them; 12 months if all are done, then the whole archive), rapid only,
  40-200 plies, no abandoned games (`LONG_*` in config.py). Old games from when I was ~800 are not wanted.
- Keep the suspense so viewers stay to the end: nothing on screen may show what happens later in the game. The
  eval graph and the move list only show the moves played so far (2026-10-21: the full-game graph spoiled it).
- Title: Claude's story title (max 70 chars), no hashtags in the title; the description carries the summary,
  YouTube chapter timestamps, opening, game link and the fixed hashtags. Category Gaming, uploaded private.
- Thumbnail: generated (key position, red arrow on the decisive move, 2-4 big words, eval swing) and set via the
  API; if YouTube refuses (channel not phone-verified), the PNG stays in `data/temp/long/` to upload by hand.
- No plain-render fallback for long videos: if anything fails, nothing is uploaded.
- If a long run fails, the full editor output is in `data/temp/long/editor.log`. Re-running the same game (paste its
  ID in the bat) reuses the analysis and the script (`--resume`), so only voice + render run again (~35 min).
- On Windows npx/Remotion can exit with -1 after the file is finished (seen 2026-10-21); `render()` accepts a
  render whose length matches the timeline. An expired/revoked YouTube token now opens the sign-in again.

## Project layout
```
main.py, config.py                    entry point + settings (CHESS_USERNAME / STOCKFISH_PATH also via env vars)
run_chess_automation.bat              asks Short/Long, then an optional game link/ID; runs main.py --format ...
setup_editor.bat                      one-time editor setup (safe to re-run)
src/                                  chess_api (incl. get_game_by_id), youtube_api, utils (titles), editor_bridge
                                      (voice rotation, style history), video_gen + music_manager (plain fallback)
video_editor/make_short.py            the editor CLI; pipeline/ (analysis, story, styles, writers, voice,
                                      timeline, render); studio/ (Remotion 4.0.534 React project)
video_editor/make_long.py             the long-video CLI; pipeline/long/ (openings + Lichess opening tables,
                                      deep engine pass, motifs, schema, writer, briefs, timeline);
                                      studio/src/long/ (ChessLong 1920x1080 + ChessThumb 1280x720)
tests/                                manual check scripts (python -m tests.test_pick / test_stockfish from the root)
scripts/create_dummy_music.py         makes a test music file for the plain renderer
data/ (git-ignored)                   history.json, history_long.json, editor_voice.json, editor_style.json,
                                      editor_style_long.json, token.json, temp/ (temp/long/ = long work files)
assets/music/ (git-ignored)           background music for the plain render only (copyrighted, never commit)
edits/ (git-ignored)                  sample videos and previews
```

## How a run works
`main.py --format short|long [game]` -> picks a game (chosen ID via `get_game_by_id`, else a random game not in
that format's history) -> Long: `editor_bridge.make_long_video` runs `make_long.py` (below), uploads
`data/temp/long/long.mp4` with title/description/tags from `upload.json`, sets the thumbnail, records
`history_long.json` and `editor_style_long.json`. Short:
`src/editor_bridge.py` runs `video_editor/.venv/Scripts/python.exe video_editor/make_short.py` with the next voice
and `--recent data/editor_style.json` -> uploads `data/temp/edited.mp4` with the story title -> after a
successful upload records the game in history, the voice and the style/title.
If the editor is not set up or fails, `main.py` falls back to the original plain render (`src/video_gen.py`).

Inside `video_editor/`:
1. `pipeline/analysis.py`: Stockfish eval/best move/quality for every ply (win%-based blunder/mistake labels), clocks.
2. `pipeline/story.py`: winner, how it ended, turning point (decisive ply), puzzle ("find the move") position.
3. `pipeline/styles.py` picks the style and its look. `pipeline/writer_claude.py` writes the commentary script and
   title with `claude -p` (or the Anthropic API if `ANTHROPIC_API_KEY` is set), validates it
   (`pipeline/script_schema.py`), then a second Claude pass fact-checks every sentence against the move table and
   the style facts. Style rules and an example script (`pipeline/example_script.json`, hand-written for my
   Caro-Kann game) are in the prompt. If Claude is unavailable or the script stays invalid ->
   `pipeline/writer_template.py` (plain, always valid, original look).
4. `pipeline/voice.py`: Kokoro narrator. The ONNX model is patched once to output phoneme durations, so every
   word has an exact timestamp (models live in `video_editor/models/`).
5. `pipeline/timeline.py`: voices each line, places moves on the spoken word, captions (1-3 words, active word
   highlighted), effects, sound effects, hook opener / rewind transition / puzzle countdown / CHECKMATE or RESIGNS
   slam, and automatic polish (?? badges on blunders, answer arrow). Writes `studio/src/timeline.json`
   (incl. `look` colours and `headline`), `game.json`, `studio/public/voice.wav`.
6. `studio/`: Remotion project that draws everything (colours come from `LOOK` in `studio/src/story.ts`, with the
   original palette as default); `pipeline/render.py` renders it and masters audio to -14 LUFS.

Long videos (`make_long.py`): analysis + story as above (cached in the work folder for re-runs) ->
`long/openings.py` (opening name/ECO and where the game leaves the named book lines) -> `long/deep.py` (MultiPV-3
at depth 18 on every mistake/blunder and the turning point, the best reply, accuracy/stats) and `long/motifs.py`
(rule-checked fork/pin/skewer/discovery/mate-threat/hanging facts) -> style (same detectors as Shorts; long
briefs in `long/briefs.py`, last 3 long styles avoided) -> `long/writer_long.py`: Claude outlines, writes the
script (`long/schema_long.py`: cold open, 3-6 game chapters, lessons, outro; lines with moves/spread/skip,
"what if" variations, think pauses, panel cards, effects), every variation is played and scored by Stockfish
and fed to the fact-check pass, then a fit pass if the voiced video is outside 5.5-9 min ->
`long/timeline_long.py` (board states incl. variation positions, events, cards, chapter cards, YouTube chapter
times) writes `studio/public/long/props.json` + `voice.wav` -> Remotion `ChessLong` (render ~1-2 h) and
`ChessThumb` (thumbnail) -> `<work>/upload.json`.

## Setup status (as of 2026-10-27)
Set up and running daily on this Windows PC since 2026-10-12 (Python 3.12 editor venv via uv; main Python is
3.14). Fixed on the first Windows run: a lockfile generated on Linux (regenerated) and `setup_editor.bat` failing
on re-run (now keeps an existing venv). Claude Code is logged in; Claude writes the commentary.
Long videos work end to end since 2026-10-22 (first upload 59fgXVzeAt0; a render takes ~26 min for 8 min of
video, the whole run ~1-1.5 h). The YouTube token expired on 2026-10-21 and was renewed by signing in again.
2026-10-22: Shorts crashed in `styles.choose` on an empty entry in `data/editor_style.json` (an upload recorded
without a style); the entry was removed, `choose` skips such entries and `remember_style` no longer writes them.

## Testing without uploading
From the project root:
`video_editor\.venv\Scripts\python video_editor\make_short.py --pgn data\temp\game.pgn --out test.mp4 --username houssem999 --stockfish "<STOCKFISH_PATH>"`
- `--no-render` stops after the timeline (then `cd video_editor\studio` and `npx remotion studio` to preview).
- `--writer template` skips Claude; `--script path\to\script.json` re-renders with an edited script.
- `--style <id>` forces a storytelling style; `--recent data\editor_style.json` makes it avoid recent styles/titles.
- Long video: `video_editor\.venv\Scripts\python video_editor\make_long.py --pgn data\temp\game.pgn --out long.mp4
  --work data\temp\long_test --username houssem999 --stockfish "<STOCKFISH_PATH>" --no-render` (add `--thumb-only`
  to also make the thumbnail; `--script <work>\script.json` re-voices an edited script without Claude). Preview
  with `npx remotion studio` (composition ChessLong) or `npx remotion still src/index.ts ChessLong f.png --frame=N`.
- `python -m tests.test_pick` checks the random game pick for both formats (no video, no upload).
- Cheap visual checks: render only a frame range (`npx remotion render src/index.ts ChessShort out.mp4
  --frames=0-200 --scale=0.5`) or one frame (`npx remotion still ... --frame=N`) in `video_editor\studio`.
- `python main.py <id that doesn't exist>` exercises the bat/main path and stops before making anything.
A full Short render takes ~10 minutes, a long one ~26 minutes. The owner prefers not to wait on full test
renders unless needed; `python main.py` runs upload to YouTube, so test with the editor CLIs instead.

## Known issues (not fixed on purpose / owner's call)
- Playlist adds fail with 403: `YOUTUBE_SCOPES` only has `youtube.upload`. The owner manages the playlist by hand.
- `studio/src/ChessShort.tsx` skips the move sound of ply 37 in every video (`.filter((b) => b.ply !== 37)`),
  a leftover from the example game.
- `assets/music/DxDiag.txt` (a system report) and `data/history.json` were in the first commit; they are
  untracked now but remain in that commit's history. Publish from a fresh history if the repo goes public.

## Housekeeping
- `edits/` holds sample videos and previews and is git-ignored, as are the venv, models, node_modules,
  generated studio files, `data/`, music, logs and secrets.
- Sound effects are Kenney CC0 + synthesised; pieces are cburnett (python-chess); fonts Anton/Inter (OFL).
