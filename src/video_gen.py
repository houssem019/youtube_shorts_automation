import chess
import chess.pgn
import chess.svg
from html2image import Html2Image
import io
import os
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip, afx
import logging
import PIL.Image
import PIL.ImageChops
import PIL.ImageDraw
import PIL.ImageFont
from gtts import gTTS
from src.stockfish_engine import StockfishEngine
from src.music_manager import MusicManager

# Monkey-patch ANTIALIAS for moviepy compatibility with Pillow 10+
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

logger = logging.getLogger(__name__)

class ChessVideoGenerator:
    def __init__(self, temp_dir="data/temp", stockfish_path=r"C:\Users\Cognira\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"):
        self.temp_dir = temp_dir
        self.stockfish_path = stockfish_path
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        # Initialize Html2Image
        self.hti = Html2Image(output_path=self.temp_dir)

    def _convert_move_to_speech(self, move_san, board):
        """
        Converts chess notation to natural speech.
        Examples:
        - "Nf3" -> "Knight to f3"
        - "Nxe5" -> "Knight takes e5"
        - "O-O" -> "Castles kingside"
        - "e4" -> "Pawn to e4"
        - "Qh5+" -> "Queen to h5 check"
        - "Qxf7#" -> "Queen takes f7 checkmate"
        """
        text = move_san

        # Handle castling
        if text == "O-O":
            return "Castles kingside"
        elif text == "O-O-O":
            return "Castles queenside"

        # Piece names
        piece_names = {
            'K': 'King',
            'Q': 'Queen',
            'R': 'Rook',
            'B': 'Bishop',
            'N': 'Knight'
        }

        # Start building the speech
        speech_parts = []

        # Determine piece
        if text[0] in piece_names:
            speech_parts.append(piece_names[text[0]])
            text = text[1:]
        else:
            speech_parts.append("Pawn")

        # Check for capture
        if 'x' in text:
            speech_parts.append("takes")
            text = text.replace('x', '')
        else:
            speech_parts.append("to")

        # Get destination square (last 2 chars before special symbols)
        destination = ""
        for char in text:
            if char.isalnum():
                destination += char

        # Take last 2 characters as the square
        if len(destination) >= 2:
            square = destination[-2:]
            speech_parts.append(square)

        # Check for check or checkmate
        if '#' in move_san:
            speech_parts.append("checkmate")
        elif '+' in move_san:
            speech_parts.append("check")

        return " ".join(speech_parts)

    def pgn_to_images_and_audio(self, pgn_string):
        """
        Parses PGN and generates an image and audio for each move.
        Returns a list of tuples (image_path, audio_path, speech_text).
        """
        pgn = io.StringIO(pgn_string)
        game = chess.pgn.read_game(pgn)
        board = game.board()

        assets = []

        # Start from first move (no initial board state)
        move_count = 0

        # Initialize Stockfish engine
        engine = None
        try:
            if self.stockfish_path:
                engine = StockfishEngine(self.stockfish_path)
                engine.__enter__()
        except Exception as e:
            logger.error(f"Failed to initialize Stockfish: {e}")

        prev_score = None # Track previous evaluation for classification

        try:
            for i, move in enumerate(game.mainline_moves(), 1):
                # Limit to 90 moves to keep video under 3 minutes
                if move_count >= 90:
                    logger.info(f"Stopping at move {move_count} to keep video under 3 minutes")
                    break

                # Get SAN before pushing the move
                move_san = board.san(move)

                # Convert to intelligent speech
                speech_text = self._convert_move_to_speech(move_san, board)

                # Get evaluation BEFORE move to establish baseline
                if i == 1 and engine:
                     try:
                        start_eval = engine.get_evaluation(board)
                        if start_eval['type'] == 'cp':
                            prev_score = start_eval['value']
                        else:
                            prev_score = 99999 if start_eval['value'] > 0 else -99999 # Mate
                     except:
                        pass

                is_white_turn = board.turn # True if White to move

                board.push(move)

                # Get evaluation AFTER move
                eval_text = ""
                move_class = ""
                current_score_val = None

                if engine:
                    try:
                        eval_data = engine.get_evaluation(board)

                        # Format text
                        if eval_data['type'] == 'mate':
                            eval_text = f"M{abs(eval_data['value'])}"
                            if eval_data['value'] < 0:
                                eval_text = f"-M{abs(eval_data['value'])}"
                            current_score_val = 99999 if eval_data['value'] > 0 else -99999
                        else:
                            # Convert centipawns to pawns
                            score = eval_data['value'] / 100.0
                            eval_text = f"{score:+.1f}"
                            current_score_val = eval_data['value']

                        # Classify move
                        if prev_score is not None and current_score_val is not None:
                            move_class = self._classify_move(prev_score, current_score_val, is_white_turn)

                        prev_score = current_score_val

                    except Exception as e:
                        logger.error(f"Evaluation failed: {e}")

                self._save_board_image(board, i, speech_text, eval_text, move_class)
                audio_path = self._generate_audio(speech_text, i)

                assets.append((os.path.join(self.temp_dir, f"move_{i}.png"), audio_path, speech_text))
                move_count += 1
        finally:
            if engine:
                engine.__exit__(None, None, None)

        return assets

    def _generate_audio(self, text, move_number):
        """
        Generates TTS audio for the given text.
        """
        try:
            tts = gTTS(text=text, lang='en')
            filename = f"move_{move_number}.mp3"
            path = os.path.join(self.temp_dir, filename)
            tts.save(path)
            return path
        except Exception as e:
            logger.error(f"Failed to generate audio for '{text}': {e}")
            return None

    def _classify_move(self, prev_score, current_score, is_white_turn):
        """
        Classifies the move based on score change.
        """
        # Calculate delta from the perspective of the player who just moved
        if is_white_turn:
            delta = current_score - prev_score
        else:
            delta = prev_score - current_score

        # Thresholds (in centipawns)
        if delta >= -20:
            return "Best"
        elif delta >= -50:
            return "Good"
        elif delta >= -100:
            return "Inaccuracy"
        elif delta >= -200:
            return "Mistake"
        else:
            return "Blunder"

    def _save_board_image(self, board, move_number, subtitle_text="", eval_text="", move_class=""):
        # Generate SVG with explicit size
        svg_data = chess.svg.board(board=board, size=800)

        # Wrap SVG in HTML to ensure it renders
        html_content = f"""
        <html>
        <body style="margin: 0; padding: 0; background-color: white;">
            {svg_data}
        </body>
        </html>
        """

        output_filename = f"move_{move_number}.png"

        # html2image screenshot - 1000x1000 to ensure full board with generous padding
        self.hti.screenshot(html_str=html_content, save_as=output_filename, size=(1000, 1000))

        # Crop the image to remove white space
        img_path = os.path.join(self.temp_dir, output_filename)
        self._crop_image(img_path)

        # Add subtitle directly to image using PIL
        if subtitle_text:
            self._add_subtitle_to_image(img_path, subtitle_text)

        # Add evaluation overlay
        if eval_text:
            self._add_eval_overlay(img_path, eval_text, move_class)

    def _crop_image(self, img_path):
        """
        Crops white space from the image and centers the board.
        """
        try:
            img = PIL.Image.open(img_path)

            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get bounding box of non-white content
            bg = PIL.Image.new('RGB', img.size, (255, 255, 255))
            diff = PIL.ImageChops.difference(img, bg)
            bbox = diff.getbbox()

            if bbox:
                # Crop to the bounding box
                img = img.crop(bbox)
                # Save back
                img.save(img_path)
        except Exception as e:
            logger.error(f"Failed to crop image {img_path}: {e}")

    def _add_subtitle_to_image(self, img_path, text):
        """
        Adds subtitle text directly to the image using PIL.
        """
        try:
            img = PIL.Image.open(img_path)

            # Try to use a nice font, fall back to default if not available
            try:
                font = PIL.ImageFont.truetype("arial.ttf", 60)
            except:
                font = PIL.ImageFont.load_default()

            # Get text size for measuring
            temp_draw = PIL.ImageDraw.Draw(img)
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Expand canvas to add space for subtitle below the board
            img_width, img_height = img.size
            subtitle_padding = 30  # Space above and below text
            new_height = img_height + text_height + subtitle_padding * 2

            # Create new image with extra space at bottom
            new_img = PIL.Image.new('RGB', (img_width, new_height), 'black')
            new_img.paste(img, (0, 0))

            # Draw subtitle in the new space
            draw = PIL.ImageDraw.Draw(new_img)
            x = (img_width - text_width) // 2
            y = img_height + subtitle_padding  # Just below the board

            # Draw text with black outline (stroke)
            draw.text((x, y), text, font=font, fill='white', stroke_width=3, stroke_fill='black')

            # Save the modified image
            new_img.save(img_path)
            logger.info(f"Added subtitle '{text}' to {img_path}")
        except Exception as e:
            logger.error(f"Failed to add subtitle to {img_path}: {e}")

    def _add_eval_overlay(self, img_path, text, move_class=""):
        """
        Adds evaluation text and move classification above the board on the left.
        """
        try:
            img = PIL.Image.open(img_path)

            try:
                font_eval = PIL.ImageFont.truetype("arial.ttf", 40)
                font_class = PIL.ImageFont.truetype("arial.ttf", 50)
            except:
                font_eval = PIL.ImageFont.load_default()
                font_class = PIL.ImageFont.load_default()

            # Calculate space needed above the board
            top_padding = 20
            eval_height = 50
            class_height = 60 if move_class else 0
            total_top_space = top_padding + eval_height + class_height + top_padding

            # Expand canvas to add space above the board
            img_width, img_height = img.size
            new_height = img_height + total_top_space

            # Create new image with extra space at top
            new_img = PIL.Image.new('RGB', (img_width, new_height), 'black')
            new_img.paste(img, (0, total_top_space))

            # Draw on the new image
            draw = PIL.ImageDraw.Draw(new_img)

            # Position: Top-left with padding
            x = 30
            y = top_padding

            # Draw Eval
            draw.text((x, y), f"Eval: {text}", font=font_eval, fill='yellow', stroke_width=2, stroke_fill='black')

            # Draw Classification below eval
            if move_class:
                y_class = y + eval_height

                # Color coding
                color = "white"
                if move_class == "Best": color = "#90ee90" # Light green
                elif move_class == "Good": color = "#90ee90"
                elif move_class == "Inaccuracy": color = "yellow"
                elif move_class == "Mistake": color = "orange"
                elif move_class == "Blunder": color = "red"

                draw.text((x, y_class), move_class, font=font_class, fill=color, stroke_width=2, stroke_fill='black')

            new_img.save(img_path)
            logger.info(f"Added eval '{text}' and class '{move_class}' above board to {img_path}")
        except Exception as e:
            logger.error(f"Failed to add eval overlay to {img_path}: {e}")

    def create_short(self, pgn_string, output_path="output.mp4", background_music=None, music_volume=0.1, track_music=True):
        """
        Creates a video from the PGN string with subtitles.
        YouTube Shorts now support up to 3 minutes.
        If background_music is None and track_music is True, automatically selects music via MusicManager.
        """
        try:
            assets = self.pgn_to_images_and_audio(pgn_string)
            clips = []

            for img_path, audio_path, speech_text in assets:
                if os.path.exists(img_path):
                    # Create Image Clip
                    img_clip = ImageClip(img_path)

                    # Add Audio if available
                    if audio_path and os.path.exists(audio_path):
                        audio_clip = AudioFileClip(audio_path)
                        duration = audio_clip.duration + 0.2  # Add a little pause
                        img_clip = img_clip.set_duration(duration)
                        img_clip = img_clip.set_audio(audio_clip)
                    else:
                        # Fallback duration if no audio
                        duration = 1.0
                        img_clip = img_clip.set_duration(duration)

                    clips.append(img_clip)
                else:
                    logger.warning(f"Image not found: {img_path}")

            if not clips:
                logger.error("No clips generated.")
                return False

            final_clip = concatenate_videoclips(clips, method="compose")

            # Select background music if not provided
            if background_music is None and track_music:
                music_manager = MusicManager()
                background_music = music_manager.get_background_music()
                if background_music:
                    logger.info(f"Auto-selected music: {background_music}")

            # Add Background Music
            if background_music and os.path.exists(background_music):
                try:
                    logger.info(f"Adding background music: {background_music}")
                    music_clip = AudioFileClip(background_music)

                    # Loop music if shorter than video
                    if music_clip.duration < final_clip.duration:
                        music_clip = afx.audio_loop(music_clip, duration=final_clip.duration)
                    else:
                        music_clip = music_clip.subclip(0, final_clip.duration)

                    # Adjust volume
                    music_clip = music_clip.volumex(music_volume)

                    # Mix audio - handle case where original audio might be None
                    original_audio = final_clip.audio
                    if original_audio is not None:
                        final_audio = CompositeAudioClip([original_audio, music_clip])
                    else:
                        final_audio = music_clip
                    final_clip = final_clip.set_audio(final_audio)
                    logger.info(f"Background music added successfully")
                except Exception as e:
                    logger.error(f"Failed to add background music: {e}")

            # Resize for Shorts (9:16)
            final_clip = final_clip.resize(width=1080)
            final_clip = final_clip.on_color(size=(1080, 1920), color=(0,0,0), pos='center')

            final_clip.write_videofile(output_path, fps=24, audio_codec='aac')
            logger.info(f"Video saved to {output_path} (duration: {final_clip.duration:.1f}s)")
            return True

        except Exception as e:
            logger.error(f"Error creating video: {e}")
            return False
