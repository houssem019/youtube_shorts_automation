import chess
import chess.engine
import os

class StockfishEngine:
    def __init__(self, binary_path, time_limit=0.1):
        self.binary_path = binary_path
        self.time_limit = time_limit
        self.engine = None

    def __enter__(self):
        # Ensure the binary path is correct, handling potential missing .exe extension on Windows
        if os.name == 'nt' and not self.binary_path.endswith('.exe'):
             if os.path.exists(self.binary_path + '.exe'):
                 self.binary_path += '.exe'

        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.binary_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Stockfish binary not found at {self.binary_path}")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.engine:
            self.engine.quit()

    def get_evaluation(self, board):
        """
        Returns a dictionary with 'type' ('cp' or 'mate') and 'value'.
        Positive values favor White, negative favor Black.
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized. Use 'with' statement.")

        info = self.engine.analyse(board, chess.engine.Limit(time=self.time_limit))
        score = info["score"].white()

        if score.is_mate():
            return {"type": "mate", "value": score.mate()}
        else:
            return {"type": "cp", "value": score.score()}
