import numpy as np
from moviepy.audio.AudioClip import AudioArrayClip
import os

def create_dummy_music(filename="assets/music/test_music.mp3", duration=5):
    # Create a simple sine wave
    rate = 44100
    t = np.linspace(0, duration, duration*rate)
    # 440 Hz sine wave (A4 note)
    audio = np.sin(2 * np.pi * 440 * t)

    # Make it stereo
    audio = np.array([audio, audio]).T

    clip = AudioArrayClip(audio, fps=rate)

    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    clip.write_audiofile(filename)
    print(f"Created dummy music: {filename}")

if __name__ == "__main__":
    create_dummy_music()
