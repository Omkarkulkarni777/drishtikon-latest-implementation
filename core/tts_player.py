# core/tts_player.py
# ================================================================
#  TTS PLAYER (Commit 6)
#  - Real-time streamed PCM playback using sounddevice
#  - Supports: play(), pause(), resume(), stop()
#  - Non-blocking playback thread
# ================================================================

import os
import time
import threading
import sounddevice as sd
import soundfile as sf   # sounddevice requires soundfile to read PCM


class TTSPlayer:
    def __init__(self):
        self._thread = None
        self._is_paused = False
        self._is_stopped = False
        self._lock = threading.Lock()

    def is_playing(self):
        """
        Check if playback is currently active.
        """
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------
    # Internal threaded playback loop
    # ------------------------------------------------------------
    def _playback_loop(self, audio_path):
        try:
            data, samplerate = sf.read(audio_path, dtype='int16')
        except Exception as e:
            print(f"[TTSPlayer] ERROR loading WAV: {e}")
            self._thread = None
            return

        # Flatten mono to (samples, 1)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)

        total_frames = data.shape[0]
        frame_index = 0

        # Stream object
        stream = sd.OutputStream(
            samplerate=samplerate,
            channels=data.shape[1],
            dtype='int16',
            blocksize=1024
        )

        stream.start()

        print("[TTSPlayer] Streaming start...")

        while frame_index < total_frames:

            # STOP
            if self._is_stopped:
                break

            # PAUSE
            if self._is_paused:
                time.sleep(0.05)
                continue

            # Next chunk
            chunk_end = min(frame_index + 1024, total_frames)
            chunk = data[frame_index:chunk_end]

            try:
                stream.write(chunk)
            except Exception as e:
                print(f"[TTSPlayer] ERROR during stream.write: {e}")
                break

            frame_index = chunk_end

        stream.stop()
        stream.close()
        self._thread = None
        print("[TTSPlayer] Streaming finished.")

    # ------------------------------------------------------------
    # Public API: play
    # ------------------------------------------------------------
    def play(self, audio_path):
        """
        Start audio playback in a background thread.
        """

        if not isinstance(audio_path, str) or not os.path.isfile(audio_path):
            print("[TTSPlayer] Invalid path passed to play()")
            return

        print(f"[TTSPlayer] Starting new playback thread: {audio_path}")

        # Stop any existing playback
        self.stop()
        time.sleep(0.05)

        self._is_paused = False
        self._is_stopped = False

        # Start thread
        self._thread = threading.Thread(
            target=self._playback_loop,
            args=(audio_path,),
            daemon=True
        )
        self._thread.start()

    # ------------------------------------------------------------
    # Public API: pause
    # ------------------------------------------------------------
    def pause(self):
        """
        Pause playback by setting pause flag.
        """
        if self._thread:
            print("[TTSPlayer] Paused.")
            self._is_paused = True

    # ------------------------------------------------------------
    # Public API: resume
    # ------------------------------------------------------------
    def resume(self):
        """
        Resume playback.
        """
        if self._thread:
            print("[TTSPlayer] Resumed.")
            self._is_paused = False

    # ------------------------------------------------------------
    # Public API: stop
    # ------------------------------------------------------------
    def stop(self):
        """
        Stop playback completely.
        """
        if self._thread:
            print("[TTSPlayer] STOP called.")
            self._is_stopped = True
            self._is_paused = False
            time.sleep(0.05)
            sd.stop()
        self._thread = None


# Dual Engine TTS Player
tts_main = TTSPlayer()
tts_summary = TTSPlayer()
tts_prompt = TTSPlayer()
