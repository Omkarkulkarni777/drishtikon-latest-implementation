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

def select_output():
    for i, dev in enumerate(sd.query_devices()):
        if dev["name"] == "pulse" and dev["max_output_channels"] > 0:
            sd.default.device = (None, i)
            sd.default.samplerate = int(dev["default_samplerate"])
            sd.default.channels = 2
            print(f"[TTS] Using PulseAudio output (index {i})")
            return

    # Fallback: default device (never crash)
    sd.default.device = None
    print("[TTS] PulseAudio not found, using default output")


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

        if len(data.shape) == 1:
            data = data.reshape(-1, 1)

        total_frames = data.shape[0]
        frame_index = 0
        max_retries = 3
        stream = None

        for attempt in range(max_retries):
            try:
                sd.stop()
                time.sleep(0.05 * (attempt + 1))
                
                stream = sd.OutputStream(
                    samplerate=samplerate,
                    channels=data.shape[1],
                    dtype="int16",
                    blocksize=1024,
                )
                stream.start()
                # print("[TTSPlayer] Streaming started...")
                break
            except Exception as e:
                print(f"[TTSPlayer] Stream open attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    self._stop_flag = False
                    self._thread = None
                    return
                time.sleep(0.1 * (attempt + 1))

        try:
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
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            self._stop_flag = False
            self._thread = None
            # print("[TTSPlayer] Streaming finished.")

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
        try:
            if self._thread and self._thread.is_alive():
                print("[TTSPlayer] STOP called.")
                self._stop_flag = True
                sd.stop()
                self._thread.join(timeout=1.5)
        except Exception as e:
            print(f"[TTSPlayer] Stop error: {e}")
        finally:
            self._thread = None
            self._stop_flag = False


    # ------------------------------------------------------------
    # Public API: wait
    # ------------------------------------------------------------
    def wait(self):
        """
        Blocking main thread
        """
        while self.is_playing() and not os.path.exists("/tmp/stop.txt"):
            time.sleep(0.05)

# ================================================================
# TTSPlayer instance
# ================================================================
tts_main = TTSPlayer()
