import time
from core.stt import listen
from core.tts_player import tts_prompt
from core.tts import speak, speak_blocking

VALID_COMMANDS = {
    "resume": ['resume', 'continue', 'start'],
    "quit": ['quit', 'exit', 'end', 'read', 'detect', 'stop'],
    "summary": ['summary', 'summarize', 'summarise']
}

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
            speak_blocking("I did not catch that. Please try again.")
            time.sleep(1)
    return None 