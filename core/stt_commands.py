# core/stt_commands.py
# ================================================================
# STT COMMAND NORMALIZATION + RETRY LOGIC
# Cleaned to match new architecture (no speak_blocking, no tts_prompt)
# ================================================================
from collections import Counter
import re
from core.stt import listen
from core.prompts import vc_retry_p
from core.tts_player import tts_main
from core.playback_controls import play

VALID_COMMANDS = {
    # Goal: Resume, Continue, Start
    "p": ["resume", "continue", "start", "pee", "pay", "play", "okay", "go", "read"],
    
    # Goal: Quit, Exit, Stop
    "q": ["quit", "exit", "excerpt", "end", "detect", "stop", "quick", "queue", "done", "cancel", "out"],
    
    # Goal: Summary, Summarize
    "m": ["summary", "summarize", "summarise", "somebody", 'summer'],
    
    # Goal: Query, Question, Ask
    "x": ["query", "doubt", "question", "axe", "ask", "text", "next", "tax"],
    
    # Goal: Search, RAG, Look up, Find
    "r": ["search", "surge", "suraj", "rag", "look", "find", "track", "are", "arg", "art", "rock", "wreck"],
    
    # Goal: Yes when asked to continue previous task
    "y": ["yes", "yep", "yeah", "sure", "great"]
}

def normalize_command(text):
    """
    Turn raw STT text into canonical command:
    Returns "resume", "quit", "summary", "doubt", "search" or None.
    """
    if not text:
        return "p"

    text = text.lower().strip()

    for command, variants in VALID_COMMANDS.items():
        for v in variants:
            if v in text:
                return command
    return None

def helper_for_exit(stt_text):
    if stt_text:
        stt_text = stt_text.lower()
        words = re.split(r'\b\W+\b', stt_text)
        for ix in range(len(words)):
            words[ix] = words[ix].strip(".,;!?")
        counter = Counter(words)
        if 2 * counter['exit'] / len(words) > 1:
            command = normalize_command(stt_text)
            return command
    return stt_text

def listen_for_command(max_attempts=2, is_question=False):
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
        if is_question:
            command = stt_text
            if stt_text:
                stt_text = stt_text.lower()
                words = re.split(r'\b\W+\b', stt_text)
                for ix in range(len(words)):
                    words[ix] = words[ix].strip(".,;!?")
                counter = Counter(words)
                if 2 * counter['exit'] / len(words) > 1:
                    command = normalize_command(stt_text)
        else:
            command = normalize_command(stt_text)

        if command:
            print(f"[VOICE] Recognized command: {command}")
            return command

        if attempts < max_attempts:
            play(tts_main, vc_retry_p)
    return None
