# core/tts_player.py
# ================================================================
#  TTS PLAYER (SKELETON - Commit 2)
#  Future threaded audio engine for pause/resume/stop capabilities.
#  For now, it contains empty methods so nothing in the system breaks.
# ================================================================

class TTSPlayer:
    def __init__(self):
        self._thread = None
        self._is_paused = False
        self._is_stopped = False

    # ------------------------------------------------------------
    # Future: generate audio + play in a background thread
    # ------------------------------------------------------------
    def play(self, audio_path_or_text):
        """
        Future method to:
        - accept text or a wav file path
        - call Google TTS (if needed)
        - spawn playback thread
        For now: stub (does nothing).
        """
        print("[TTSPlayer] play() called (stub).")

    # ------------------------------------------------------------
    # Future: Pause audio playback
    # ------------------------------------------------------------
    def pause(self):
        print("[TTSPlayer] pause() called (stub).")

    # ------------------------------------------------------------
    # Future: Resume audio playback
    # ------------------------------------------------------------
    def resume(self):
        print("[TTSPlayer] resume() called (stub).")

    # ------------------------------------------------------------
    # Future: Stop audio playback immediately
    # ------------------------------------------------------------
    def stop(self):
        print("[TTSPlayer] stop() called (stub).")


# Global singleton
tts = TTSPlayer()
