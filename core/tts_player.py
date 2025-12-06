# core/tts_player.py
# ================================================================
# TTS PLAYER (Simplified + Hardened for Raspberry Pi)
# - Non-blocking PCM playback using sounddevice
# - Supports: play(), stop(), is_playing()
# - No pause/resume; higher-level logic restarts sentences
# - Designed for universal flush (all engines stop before new play)
# ================================================================

import os
import time
import threading
import sounddevice as sd
import soundfile as sf


class TTSPlayer:
    def __init__(self):
        self._thread = None
        self._stop_flag = False

    # ------------------------------------------------------------
    # Check if playing
    # ------------------------------------------------------------
    def is_playing(self):
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------
    # Internal threaded playback loop
    # ------------------------------------------------------------
    def _playback_loop(self, audio_path: str):
        try:
            data, samplerate = sf.read(audio_path, dtype="int16")
        except Exception as e:
            print(f"[TTSPlayer] ERROR loading audio: {e}")
            self._thread = None
            self._stop_flag = False
            return

        # Force shape: (frames, channels)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)

        total_frames = data.shape[0]
        frame_index = 0

        try:
            with sd.OutputStream(
                samplerate=samplerate,
                channels=data.shape[1],
                dtype="int16",
                blocksize=1024,
            ) as stream:

                print("[TTSPlayer] Streaming start...")

                while frame_index < total_frames and not self._stop_flag:
                    chunk_end = min(frame_index + 1024, total_frames)
                    chunk = data[frame_index:chunk_end]

                    try:
                        stream.write(chunk)
                    except Exception as e:
                        print(f"[TTSPlayer] ERROR during stream.write: {e}")
                        break

                    frame_index = chunk_end

        finally:
            # reset state
            self._stop_flag = False
            self._thread = None
            print("[TTSPlayer] Streaming finished.")

    # ------------------------------------------------------------
    # Public API: play
    # ------------------------------------------------------------
    def play(self, audio_path: str):
        """
        Start audio playback in a background thread.
        Any existing playback is fully stopped first.
        """
        if not isinstance(audio_path, str) or not os.path.isfile(audio_path):
            print("[TTSPlayer] Invalid path passed to play()")
            return

        # Ensure no old audio is running
        self.stop()
        time.sleep(0.02)

        self._stop_flag = False
        self._thread = threading.Thread(
            target=self._playback_loop,
            args=(audio_path,),
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------
    # Public API: stop
    # ------------------------------------------------------------
    def stop(self):
        """
        Stop playback completely and cleanly.
        """
        if self._thread and self._thread.is_alive():
            print("[TTSPlayer] STOP called.")
            self._stop_flag = True

            # Immediately kill all active sounddevice streams
            sd.stop()

            # Allow thread to terminate
            self._thread.join(timeout=0.2)

        self._thread = None
        self._stop_flag = False


# ================================================================
# Three-player system (main, summary, prompt)
# These can all be flushed before mode switches.
# ================================================================
tts_main = TTSPlayer()
tts_summary = TTSPlayer()
tts_prompt = TTSPlayer()
