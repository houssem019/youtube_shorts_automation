import argparse
import logging
import os
import sys
from src.chess_api import get_game_by_id, get_random_unedited_game, get_recent_good_game
from src.video_gen import ChessVideoGenerator
from src.youtube_api import YouTubeUploader
from src.utils import load_history, save_history, get_game_id, get_game_metadata, get_long_metadata
from src.music_manager import MusicManager
from src.editor_bridge import make_edited_short, make_long_video, remember_style, remember_voice
from config import (CHESS_USERNAME, TEMP_DIR, BACKGROUND_MUSIC_VOLUME, EDITOR_ENABLED, HISTORY_FILE,
                    LONG_HISTORY_FILE, LONG_STYLE_FILE, LONG_WORK_DIR, LONG_TIME_CLASS, LONG_MIN_PLIES,
                    LONG_MAX_PLIES, LONG_RECENT_MONTHS, LONG_RATING_MARGIN)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def pick_game(chosen_game, history, fmt):
    """The chosen game (link or ID), else a random game that has no video of this format yet. None = stop."""
    if chosen_game:
        logger.info(f"Looking for the chosen game: {chosen_game}")
        pgn = get_game_by_id(CHESS_USERNAME, chosen_game)
        if not pgn:
            logger.error("Could not find the chosen game; nothing was made or uploaded.")
            return None
        game_id = get_game_id(pgn)
        logger.info(f"Using chosen game: {game_id}")
        if game_id in history:
            logger.warning(f"This game already has a {fmt} video; it will be uploaded again.")
        return pgn

    logger.info(f"Picking a random game without a {fmt} video...")
    if fmt == "long":
        # recent games played at a good rating; longer back only when all of those have a video already
        pgn = None
        for months in (LONG_RECENT_MONTHS, LONG_RECENT_MONTHS * 2):
            pgn = get_recent_good_game(CHESS_USERNAME, history, max_plies=LONG_MAX_PLIES, min_plies=LONG_MIN_PLIES,
                                       time_class=LONG_TIME_CLASS, months=months, rating_margin=LONG_RATING_MARGIN)
            if pgn:
                break
        if not pgn:
            logger.info("No recent game fits; picking from the whole archive.")
            pgn = get_random_unedited_game(CHESS_USERNAME, history, max_plies=LONG_MAX_PLIES,
                                           min_plies=LONG_MIN_PLIES, time_class=LONG_TIME_CLASS)
    else:
        pgn = get_random_unedited_game(CHESS_USERNAME, history, max_plies=100)
    if not pgn:
        logger.error("Could not find any unprocessed games.")
        return None
    logger.info(f"Selected game: {get_game_id(pgn)}")
    return pgn


def make_short_video(game_to_process):
    """Returns (video_path, edited) where edited is the editor's result (None after the plain render)."""
    # First try the edited, commentated Short (video_editor/). If anything goes wrong there,
    # fall back to the original render so the daily upload still happens.
    video_path = None
    edited = None
    if EDITOR_ENABLED:
        logger.info("Creating the edited Short with commentary...")
        edited = make_edited_short(game_to_process, os.path.join(TEMP_DIR, "edited.mp4"))
        if edited:
            video_path = edited["path"]
        else:
            logger.warning("Edited Short failed; falling back to the plain render.")

    if not video_path:
        logger.info("Generating video...")

        # Select background music
        music_manager = MusicManager()
        background_music = music_manager.get_background_music()

        generator = ChessVideoGenerator(temp_dir=TEMP_DIR)
        video_path = os.path.join(TEMP_DIR, "output.mp4")

        # Clean up previous output
        if os.path.exists(video_path):
            os.remove(video_path)

        success = generator.create_short(
            game_to_process,
            video_path,
            background_music=background_music,
            music_volume=BACKGROUND_MUSIC_VOLUME
        )

        if not success:
            logger.error("Video generation failed.")
            return None, None
    return video_path, edited


def main(chosen_game=None, fmt="short"):
    logger.info(f"Starting Chess {'Long Video' if fmt == 'long' else 'Shorts'} Automation...")

    # 1. Load History (Shorts and long videos are tracked separately)
    history_file = LONG_HISTORY_FILE if fmt == "long" else HISTORY_FILE
    history = load_history(history_file)
    logger.info(f"Loaded {len(history)} processed games ({fmt}).")

    # 2. Pick the game
    game_to_process = pick_game(chosen_game, history, fmt)
    if not game_to_process:
        return

    # 3. Generate Video
    if fmt == "long":
        # No plain fallback for long videos: a failed edit uploads nothing.
        logger.info("Creating the long video (analysis, script, voice, render: this takes a while)...")
        edited = make_long_video(game_to_process, os.path.join(LONG_WORK_DIR, "long.mp4"))
        if not edited:
            logger.error("Long video failed; nothing was uploaded.")
            return
        video_path = edited["path"]
    else:
        video_path, edited = make_short_video(game_to_process)
        if not video_path:
            return

    # 4. Upload to YouTube
    logger.info("Uploading to YouTube...")
    uploader = YouTubeUploader()

    # Check if we can authenticate (mock check)
    if not uploader.authenticate():
        logger.warning("YouTube authentication failed. Skipping upload. Video is saved at " + video_path)
        # Don't update history if the upload fails, so we retry next time.
        return

    if fmt == "long":
        metadata = get_long_metadata(game_to_process, edited)
        logger.info(f"Title: {metadata['title']}")
        video_id = uploader.upload_video(
            video_path,
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"],
            category_id="20",  # Gaming
            privacy_status="private"  # published by hand
        )
    else:
        metadata = get_game_metadata(game_to_process, story_title=edited["title"] if edited else None)
        logger.info(f"Title: {metadata['title']}")
        video_id = uploader.upload_video(
            video_path,
            title=metadata["title"],
            description=metadata["description"],
            privacy_status="private" # Default to private for safety
        )

    if video_id:
        logger.info(f"Upload successful! Video ID: {video_id}")
        if fmt == "long":
            thumb = edited.get("thumbnail")
            if thumb and os.path.exists(thumb):
                uploader.set_thumbnail(video_id, thumb)
            remember_style(edited["style"], edited["title"], LONG_STYLE_FILE)
        else:
            if edited:
                remember_voice(edited["voice"])  # the next video uses the other narrator
                remember_style(edited["style"], edited["title"])  # the next videos use other styles and titles

            # Add to Playlist
            playlist_name = "No Edits Just Chess"
            playlist_id = uploader.get_playlist_id(playlist_name)
            if playlist_id:
                uploader.add_video_to_playlist(video_id, playlist_id)
            else:
                logger.warning(f"Playlist '{playlist_name}' not found.")
        # 5. Update History
        game_id = get_game_id(game_to_process)
        if game_id:
            history.append(game_id)
            save_history(history, history_file)
            logger.info("History updated.")
    else:
        logger.error("Upload failed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make and upload a chess video from one of your chess.com games.")
    parser.add_argument("game", nargs="?", default="", help="chess.com game link or ID (empty = random unedited game)")
    parser.add_argument("--format", choices=["short", "long"], default="short")
    args = parser.parse_args()
    main(args.game.strip() or None, args.format)
