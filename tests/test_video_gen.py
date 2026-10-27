from src.video_gen import ChessVideoGenerator
import os

def test_gen():
    gen = ChessVideoGenerator()
    # Scholar's Mate
    pgn = "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7#"
    # Let MusicManager auto-select music
    gen.create_short(pgn, "test_output.mp4")
    print("Done")

if __name__ == "__main__":
    test_gen()
