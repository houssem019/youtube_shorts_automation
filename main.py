import logging
import os
import sys
from src.chess_api import get_latest_game, get_random_old_game
from src.video_gen import ChessVideoGenerator
from src.youtube_api import YouTubeUploader
from src.utils import load_history, save_history, get_game_id, get_game_metadata
from src.music_manager import MusicManager
from config import CHESS_USERNAME, TEMP_DIR, BACKGROUND_MUSIC_VOLUME

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

def main():
    logger.info("Starting Chess Shorts Automation...")

    # 1. Load History
    history = load_history()
    logger.info(f"Loaded {len(history)} processed games.")

    # 2. Check for New Game
    logger.info(f"Checking for new games for user: {CHESS_USERNAME}")
    pgn = get_latest_game(CHESS_USERNAME)

    game_to_process = None
    is_new_game = False

    if pgn:
        game_id = get_game_id(pgn)
        if game_id and game_id not in history:
            logger.info(f"Found new game: {game_id}")
            game_to_process = pgn
            is_new_game = True
        else:
            logger.info("Latest game already processed.")

    # 3. Fallback to Old Game
    if not game_to_process:
        logger.info("Selecting a random old game...")
        # Try a few times to find an unprocessed one
        for _ in range(5):
            pgn = get_random_old_game(CHESS_USERNAME)
            if pgn:
                game_id = get_game_id(pgn)
                if game_id and game_id not in history:
                    logger.info(f"Selected old game: {game_id}")
                    game_to_process = pgn
                    break

        if not game_to_process:
            logger.error("Could not find any unprocessed games after retries.")
            return

    # 4. Generate Video
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
        return

    # 5. Upload to YouTube
    logger.info("Uploading to YouTube...")
    uploader = YouTubeUploader()

    # Check if we can authenticate (mock check)
    if not uploader.authenticate():
        logger.warning("YouTube authentication failed. Skipping upload. Video is saved at " + video_path)
        # In a real run, we might want to stop here, but for now we proceed to update history
        # ONLY if we actually uploaded? Or maybe we assume manual upload?
        # Let's assume we only update history if upload succeeds OR if we are in dev mode.
        # For now, let's NOT update history if upload fails, so we retry next time.
        return

    metadata = get_game_metadata(game_to_process)
    video_id = uploader.upload_video(
        video_path,
        title=metadata["title"],
        description=metadata["description"],
        privacy_status="private" # Default to private for safety
    )

    if video_id:
        logger.info(f"Upload successful! Video ID: {video_id}")

        # Add to Playlist
        playlist_name = "No Edits Just Chess"
        playlist_id = uploader.get_playlist_id(playlist_name)
        if playlist_id:
            uploader.add_video_to_playlist(video_id, playlist_id)
        else:
            logger.warning(f"Playlist '{playlist_name}' not found.")
        # 6. Update History
        game_id = get_game_id(game_to_process)
        if game_id:
            history.append(game_id)
            save_history(history)
            logger.info("History updated.")
    else:
        logger.error("Upload failed.")

if __name__ == "__main__":
    main()
