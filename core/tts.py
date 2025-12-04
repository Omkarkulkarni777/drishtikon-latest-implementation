# core/tts.py
# ================================================================
#  GOOGLE CLOUD TEXT-TO-SPEECH (Commit 3)
#  - Generates WAV files only
#  - NO playback (no blocking)
#  - Returns audio path for TTSPlayer to use later
# ================================================================

import os
import time
import datetime
from google.cloud import texttospeech
from google.oauth2 import service_account

from core.utils import absolute_path, ensure_dir, load_credential_path
from core.logger import log

# ================================================================
#   DIRECTORIES
# ================================================================
AUDIO_DIR = absolute_path("results", "audio_outputs")
ensure_dir(AUDIO_DIR)

# ================================================================
#   GOOGLE CREDENTIALS
# ================================================================
CRED_PATH = load_credential_path("core", "tts-key.json")

tts_client = None

def init_tts():
    global tts_client
    try:
        creds = service_account.Credentials.from_service_account_file(CRED_PATH)
        tts_client = texttospeech.TextToSpeechClient(credentials=creds)
        print("[TTS] Google TTS initialized.")
    except Exception as e:
        print(f"[TTS] ERROR loading credentials: {e}")
        tts_client = None

# Initialize on import
init_tts()

# ================================================================
#   SPEAK (Commit 3: generate audio only, no playback)
# ================================================================
def speak(text: str):
    """
    Convert text → speech using Google Cloud TTS.
    Commit 3:
        - DOES NOT PLAY AUDIO
        - RETURNS the generated WAV file path
    """

    if not tts_client:
        print("[TTS] Client not initialized.")
        return None

    t0 = time.time()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
    except Exception as e:
        log("TTS", "-", f"TTS ERROR: {e}")
        return None

    # Generate output file path
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    audio_path = absolute_path("results", "audio_outputs", f"tts_{ts}.wav")

    try:
        with open(audio_path, "wb") as f:
            f.write(response.audio_content)
    except Exception as e:
        log("TTS", "-", f"File write error: {e}")
        return None

    t1 = time.time()
    log("TTS", audio_path, f"Generated {len(text)} chars", round(t1 - t0, 2))

    # ❗RETURN THE AUDIO FILE PATH (Commit 3 change)
    return audio_path
