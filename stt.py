import sounddevice as sd
import numpy as np
from google.cloud import speech
from google.oauth2 import service_account
import os
from dotenv import load_dotenv

load_dotenv()

############################################################
#                GOOGLE CREDENTIALS (STT)
############################################################
STT_CREDENTIALS = service_account.Credentials.from_service_account_file(
    "cred/imperial-glyph-448202-p6-d36e2b69bd92.json"
)

speech_client = speech.SpeechClient(credentials=STT_CREDENTIALS)

############################################################
#                MICROPHONE RECORDING SETTINGS
############################################################
SAMPLE_RATE = 16000      # Google recommended
CHANNELS = 1             # Mono


############################################################
#                RECORD AUDIO (USB MIC)
############################################################
def record_audio(duration=4):
    """
    Records microphone audio for `duration` seconds.
    Uses default input device (your USB headset if selected in system sound).
    """

    print(f"[STT] Recording for {duration} seconds...")

    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16'
    )
    sd.wait()

    print("[STT] Recording complete.")
    return audio.tobytes()


############################################################
#                GOOGLE SPEECH-TO-TEXT
############################################################
def speech_to_text(audio_bytes):
    """
    Sends audio to Google STT and returns recognized text.
    """

    audio = speech.RecognitionAudio(content=audio_bytes)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code="en-US"
    )

    try:
        response = speech_client.recognize(
            config=config,
            audio=audio
        )
    except Exception as e:
        print("[STT] Google STT Error:", e)
        return None

    if not response.results:
        return None

    return response.results[0].alternatives[0].transcript


############################################################
#                PUBLIC LISTEN() FUNCTION
############################################################
def listen(duration=4):
    """
    High-level wrapper:
    - records `duration` seconds of audio
    - sends to Google STT
    - returns text (or None)
    """

    audio_bytes = record_audio(duration)
    text = speech_to_text(audio_bytes)

    if text:
        print(f"[STT] Heard:", text)
    else:
        print("[STT] No speech detected.")

    return text
