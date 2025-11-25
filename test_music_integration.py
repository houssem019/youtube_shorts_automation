import os
import logging
from src.video_gen import ChessVideoGenerator
from src.music_manager import MusicManager
from config import TEMP_DIR, BACKGROUND_MUSIC_VOLUME

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_music_integration():
    # 1. Ensure dummy music exists
    music_manager = MusicManager()
    music_path = music_manager.get_background_music()

    if not music_path:
        print("No music found. Please run create_dummy_music.py first.")
        return

    print(f"Testing with music: {music_path}")

    # 2. Create a short dummy PGN
    pgn = """
[Event "Test Game"]
[Site "Test"]
[Date "2023.01.01"]
[Round "1"]
[White "Player1"]
[Black "Player2"]
[Result "1/2-1/2"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7
"""

    # 3. Generate Video
    generator = ChessVideoGenerator(temp_dir=TEMP_DIR)
    output_path = os.path.join(TEMP_DIR, "test_music_output.mp4")

    if os.path.exists(output_path):
        os.remove(output_path)

    success = generator.create_short(
        pgn,
        output_path,
        background_music=music_path,
        music_volume=BACKGROUND_MUSIC_VOLUME
    )

    if success:
        print(f"Video generated successfully: {output_path}")
        # Verify file size is reasonable (indicating content)
        size = os.path.getsize(output_path)
        print(f"File size: {size} bytes")
    else:
        print("Video generation failed.")

if __name__ == "__main__":
    test_music_integration()
