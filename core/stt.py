# stt.py — Raspberry Pi version

import os
import time
import numpy as np
import sounddevice as sd
from google.cloud import speech
from google.oauth2 import service_account

from core.utils import absolute_path, load_credential_path
from core.logger import log

# ================================================================
#  MICROPHONE SETTINGS (Google recommended)
# ================================================================
SAMPLE_RATE = 16000
CHANNELS = 1


# ================================================================
#  GOOGLE CREDENTIALS
#  Expected: BASE_DIR/core/cred/stt-key.json
# ================================================================
CRED_PATH = load_credential_path("core", "stt-key.json")

speech_client = None

def init_stt():
    global speech_client

    if not os.path.exists(CRED_PATH):
        print(f"[STT] ERROR: Credential file does not exist: {CRED_PATH}")
        return

    try:
        creds = service_account.Credentials.from_service_account_file(CRED_PATH)
        speech_client = speech.SpeechClient(credentials=creds)
        print("[STT] Google Speech client initialized.")

    except Exception as e:
        print(f"[STT] ERROR loading STT credentials: {e}")
        speech_client = None


# Initialize on import
init_stt()


# ================================================================
#  AUDIO RECORDING (Raspberry Pi Safe)
# ================================================================
def record_audio(duration=4):
    """
    Records audio using ALSA (sounddevice).
    Returns raw PCM bytes.
    """

    print(f"[STT] Recording {duration}s...")

    try:
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16"
        )
        sd.wait()

    except Exception as e:
        log("STT", "-", f"Microphone error: {e}")
        print(f"[STT] Microphone error: {e}")
        return None

    print("[STT] Recording complete.")
    return audio.tobytes()


# ================================================================
#  GOOGLE SPEECH-TO-TEXT
# ================================================================
def speech_to_text(audio_bytes):
    """
    Sends audio to Google STT → returns transcript.
    """

    if not speech_client:
        print("[STT] Client not initialized.")
        return None

    audio = speech.RecognitionAudio(content=audio_bytes)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code="en-US",
        enable_automatic_punctuation=True
    )

    try:
        response = speech_client.recognize(config=config, audio=audio)

    except Exception as e:
        log("STT", "-", f"Google STT error: {e}")
        print(f"[STT] Google STT error: {e}")
        return None

    if not response.results:
        return None

    return response.results[0].alternatives[0].transcript


# ================================================================
#  PUBLIC LISTEN FUNCTION
# ================================================================
def listen(duration=4):
    """
    High-level function:
    - Records audio
    - Sends to Google STT
    - Logs time taken
    """

    t0 = time.time()

    audio_bytes = record_audio(duration)
    if not audio_bytes:
        return None

    text = speech_to_text(audio_bytes)

    t1 = time.time()

    log("STT", "-", f"Heard '{text}'" if text else "No speech detected", round(t1 - t0, 2))

    if text:
        print("[STT] Heard:", text)
    else:
        print("[STT] No speech detected.")

    return text
