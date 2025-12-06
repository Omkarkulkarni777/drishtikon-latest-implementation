# core/stt_commands.py
# ================================================================
# STT COMMAND NORMALIZATION + RETRY LOGIC
# Cleaned to match new architecture (no speak_blocking, no tts_prompt)
# ================================================================

import time
from core.stt import listen
from core.prompts import vc_retry_p
from core.tts_player import tts_main    # use tts_main as unified prompt engine


VALID_COMMANDS = {
    "resume": ["resume", "continue", "start"],
    "quit": ["quit", "exit", "end", "read", "detect", "stop"],
    "summary": ["summary", "summarize", "summarise"],
}


def normalize_command(text):
    """
    Turn raw STT text into canonical command:
    Returns "resume", "quit", "summary", or None.
    """
    if not text:
        return None

    text = text.lower().strip()

    for command, variants in VALID_COMMANDS.items():
        for v in variants:
            if v in text:
                return command
    return None


def listen_for_command(max_attempts=3):
    """
    Attempt STT max_attempts times.
    Returns the recognized command or None if failed.
    Uses pre-cached retry prompt audio.
    """

    attempts = 0

    while attempts < max_attempts:
        attempts += 1

        print(f"[VOICE] Attempt {attempts}/{max_attempts}...")
        print("[VOICE] Listening...")

        stt_text = listen()
        print(f"[VOICE] Heard: {stt_text}")

        command = normalize_command(stt_text)
        if command:
            print(f"[VOICE] Recognized command: {command}")
            return command

        if attempts < max_attempts:
            # Play retry prompt
            tts_main.stop()
            time.sleep(1.0)

            tts_main.play(vc_retry_p)
            while tts_main.is_playing():
                time.sleep(0.05)

            time.sleep(1.0)

    return None
