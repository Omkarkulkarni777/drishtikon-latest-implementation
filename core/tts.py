# core/tts.py
# ================================================================
# GOOGLE CLOUD TEXT-TO-SPEECH (Cleaned Version)
# - Generates WAV files only (LINEAR16 PCM)
# - No playback, no blocking logic
# - All prompts cached as WAV for Pi stability
# ================================================================

import os
import time
import datetime
import soundfile as sf
from google.cloud import texttospeech

from core.config import init_tts
from core.constants import AUDIO_DIR, PROMPT_CACHE_DIR
from core.utils import absolute_path, ensure_dir, load_credential_path
from core.logger import log
from core.tts_player import tts_main

# ================================================================
# DIRECTORIES
# ================================================================

ensure_dir(AUDIO_DIR)
ensure_dir(PROMPT_CACHE_DIR)

# ================================================================
# GOOGLE CREDENTIALS
# ================================================================
CRED_PATH = load_credential_path("core", "tts-key.json")
tts_client = init_tts(CRED_PATH)

# ================================================================
# speak_cached()
# - Generate once → store WAV → reuse always
# - Prevents Pi underruns because final output is LINEAR16
# ================================================================
def speak_cached(text: str, filename: str, is_detection: bool=False):
    """
    Generate TTS audio for a prompt ONCE, store as WAV, and reuse thereafter.
    Ensures Pi-safe audio playback with no MP3 decoding.
    """
    time.sleep(0.01)
        
    cached_wav = os.path.join(PROMPT_CACHE_DIR, filename)

    # Already cached? use it
    if os.path.exists(cached_wav):
        return cached_wav

    # Generate speech
    generated_path = speak("--- " + text, is_detection)

    if not generated_path or not os.path.exists(generated_path):
        print("[speak_cached] ERROR: speak() returned no audio.")
        return None

    # Convert to WAV PCM int16 (safe for Pi)
    try:
        data, samplerate = sf.read(generated_path, dtype="int16")
        sf.write(cached_wav, data, samplerate, format="WAV")
    except Exception as e:
        print(f"[speak_cached] ERROR converting to WAV: {e}")
        # Fallback: use the generated WAV (unlikely to fail)
        return generated_path

    return cached_wav


# ================================================================
# speak()
# - Generate TTS WAV
# - No playback logic inside
# - Returns path for TTSPlayer
# ================================================================
def speak(text: str, is_detection: bool=False):
    """
    Convert text → speech using Google Cloud TTS.
    Returns the path to the generated WAV.
    """
    if not tts_client:
        print("[TTS] Client not initialized.")
        return None

    t0 = time.time()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-IN",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
    )

    audio_config = texttospeech.AudioConfig(
        # Output directly as WAV (LINEAR16 PCM)
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    # Generate TTS
    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
    except Exception as e:
        log("TTS", "-", f"TTS ERROR: {e}")
        return None

    # Output filename
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if is_detection:
        audio_path = absolute_path("results", "audio_outputs", f"tts.wav")
    else:
        audio_path = absolute_path("results", "audio_outputs", f"tts_{ts}.wav")

    # Save WAV bytes
    try:
        with open(audio_path, "wb") as f:
            f.write(response.audio_content)
        print(f"[TTS] Audio written: {audio_path}")
    except Exception as e:
        log("TTS", "-", f"File write error: {e}")
        return None

    t1 = time.time()
    log("TTS", audio_path, f"Generated {len(text)} chars", round(t1 - t0, 2))

    return audio_path
