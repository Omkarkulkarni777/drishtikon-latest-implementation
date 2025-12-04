import os
import time
import datetime
import platform
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
#   Expected: /core/cred/tts-key.json  (must be a VALID service account)
# ================================================================
CRED_PATH = load_credential_path("core", "tts-key.json")

tts_client = None

def init_tts():
    global tts_client

    if not os.path.exists(CRED_PATH):
        print(f"[TTS] ERROR: Credential file missing at: {CRED_PATH}")
        return

    try:
        creds = service_account.Credentials.from_service_account_file(CRED_PATH)
        tts_client = texttospeech.TextToSpeechClient(credentials=creds)

    except Exception as e:
        print(f"[TTS] ERROR loading credentials: {e}")
        tts_client = None


# Initialize on import
init_tts()


# ================================================================
#   SPEAK FUNCTION
# ================================================================
def speak(text: str):
    """
    Google Cloud TTS (with automatic fallback).
    """

    if not tts_client:
        print("[TTS] Not initialized — speaking disabled.")
        return

    t0 = time.time()

    # Config
    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    # Generate speech
    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
    except Exception as e:
        log("TTS", "-", f"TTS ERROR: {e}")
        print(f"[TTS] Cloud TTS Error → {e}")
        return

    # Save WAV
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_path = absolute_path("results", "audio_outputs", f"tts_{ts}.wav")

    try:
        with open(out_path, "wb") as f:
            f.write(response.audio_content)
    except Exception as e:
        log("TTS", "-", f"WRITE ERROR: {e}")
        print(f"[TTS] Could not write WAV: {e}")
        return

    # Play sound — OS-dependent
    try:
        if platform.system() == "Windows":
            import winsound
            winsound.PlaySound(out_path, winsound.SND_FILENAME)
        elif platform.system() == "Linux":
            os.system(f"aplay '{out_path}' >/dev/null 2>&1")
        elif platform.system() == "Darwin":  # macOS
            os.system(f"afplay '{out_path}'")
    except Exception as e:
        print(f"[TTS] Playback error: {e}")

    t1 = time.time()
    log("TTS", out_path, f"Played {len(text)} chars", round(t1 - t0, 2))
