from src.stockfish_engine import StockfishEngine
from config import STOCKFISH_PATH
import chess

def test_engine():
    print(f"Testing Stockfish at: {STOCKFISH_PATH}")
    try:
        with StockfishEngine(STOCKFISH_PATH) as engine:
            board = chess.Board()
            print("Initial position evaluation:")
            eval_score = engine.get_evaluation(board)
            print(eval_score)

            board.push_san("e4")
            print("After e4 evaluation:")
            eval_score = engine.get_evaluation(board)
            print(eval_score)
            print("Stockfish test passed!")
    except Exception as e:
        print(f"Stockfish test failed: {e}")

if __name__ == "__main__":
    test_engine()
