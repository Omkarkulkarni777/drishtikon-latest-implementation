import os
from dotenv import load_dotenv
from google import genai
from google.oauth2 import service_account
from google.cloud import speech
from google.cloud import texttospeech

load_dotenv()

# ================================================================
# GEMINI CONFIG (NEW SDK)
# ================================================================
def init_gemini():
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API key missing. Set GEMINI_API_KEY in .env")

    # New SDK uses a client-based model
    client = genai.Client(api_key=GEMINI_API_KEY)

    print("[GEMINI] Gemini client initialized.")
    return client


# ================================================================
# GOOGLE STT CONFIG
# ================================================================
def init_stt(CRED_PATH):
    if not os.path.exists(CRED_PATH):
        print(f"[STT] ERROR: Credential file does not exist: {CRED_PATH}")
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(CRED_PATH)
        speech_client = speech.SpeechClient(credentials=creds)
        print("[STT] Google Speech client initialized.")
        return speech_client

    except Exception as e:
        print(f"[STT] ERROR loading STT credentials: {e}")
        return None


# ================================================================
# GOOGLE TTS CONFIG
# ================================================================
def init_tts(CRED_PATH):
    if not os.path.exists(CRED_PATH):
        print(f"[TTS] ERROR: Credential file does not exist: {CRED_PATH}")
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(CRED_PATH)
        tts_client = texttospeech.TextToSpeechClient(credentials=creds)
        print("[TTS] Google TTS initialized.")
        return tts_client

    except Exception as e:
        print(f"[TTS] ERROR loading credentials: {e}")
        return None
