import logging
import os
from src.chess_api import get_latest_game, get_random_old_game
from src.video_gen import ChessVideoGenerator
from config import CHESS_USERNAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_workflow():
    logger.info(f"Testing for user: {CHESS_USERNAME}")

    # 1. Test Fetching
    logger.info("Fetching latest game...")
    pgn = get_latest_game(CHESS_USERNAME)

    if not pgn:
        logger.warning("No latest game found. Trying random old game...")
        pgn = get_random_old_game(CHESS_USERNAME)

    if not pgn:
        logger.error("Could not fetch any games.")
        return

    logger.info(f"Got PGN (length: {len(pgn)})")

    # 2. Test Video Generation
    logger.info("Generating video...")
    generator = ChessVideoGenerator()
    output_path = os.path.join("data", "test_short.mp4")
    success = generator.create_short(pgn, output_path)

    if success:
        logger.info(f"Video generated successfully at {output_path}")
    else:
        logger.error("Video generation failed.")

if __name__ == "__main__":
    test_workflow()
