import time
from core.stt import listen
from core.tts_player import tts_prompt
from core.tts import speak, speak_blocking, speak_cached
from core.utils import absolute_path, ensure_dir

VALID_COMMANDS = {
    "resume": ['resume', 'continue', 'start'],
    "quit": ['quit', 'exit', 'end', 'read', 'detect', 'stop'],
    "summary": ['summary', 'summarize', 'summarise']
}

PROMPT_CACHE_DIR = absolute_path("results", "prompt_cache")
i_did_not_catch_that_but_cached_this_path = absolute_path(PROMPT_CACHE_DIR, "i_did_not_catch_that_but_cached_this.wav")

def normalize_command(text):
    """
    Turn raw STT text into canonical command string.
    Returns one of: "resume", "quit", "summary", or None.
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
    Runs Google STT max_attempts times, 
    returning the first non-None result or None if all attempts fail.
    """
    speak_blocking("Listening for command...")

    attempts = 0
    while attempts < max_attempts:
        attempts += 1

        print(f"[VOICE] Attempt {attempts}/{max_attempts}...")
        print("Listening...")
        stt_text = listen()
        print(f"[VOICE] Heard: {stt_text}")

        command = normalize_command(stt_text)
        if command:
            print(f"[VOICE] Recognized command: {command}")
            return command

        if attempts < max_attempts:
            i_did_not_catch_that_but_cached_this_p = speak_cached("I did not catch that. Please try again.", i_did_not_catch_that_but_cached_this_path)
            tts_prompt.play(i_did_not_catch_that_but_cached_this_p)
            while tts_prompt.is_playing():
                time.sleep(0.05)
            time.sleep(1)
    return None 