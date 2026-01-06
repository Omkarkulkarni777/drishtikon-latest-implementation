# stt.py — Raspberry Pi SAFE Speech-to-Text
# Fully rewritten: no RMS hacks, no hanging streams, no timeouts

import queue
import threading
import time
import sounddevice as sd
from google.cloud import speech

from core.config import init_stt
from core.constants import CHANNELS, SAMPLE_RATE
from core.utils import load_credential_path
from core.logger import log

# ================================================================
#  CONFIG
# ================================================================
LANGUAGE_CODE = "en-IN"
FALLBACK_TEXT = ""
MAX_LISTEN_SECONDS = 6  # hard wall-clock timeout

# ================================================================
#  GOOGLE CREDENTIALS
# ================================================================
CRED_PATH = load_credential_path("core", "stt-key.json")
speech_client = init_stt(CRED_PATH)

# ================================================================
#  BLOCKING (NON-STREAMING) STT
# ================================================================
def record_audio(duration=5):
    """Record raw PCM audio using ALSA (sounddevice)."""

    print(f"[STT] Recording {duration}s...")

    try:
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
        )
        sd.wait()
    except Exception as e:
        log("STT", "-", f"Microphone error: {e}")
        print(f"[STT] Microphone error: {e}")
        return None

    return audio.tobytes()


def speech_to_text(audio_bytes):
    """Send audio bytes to Google STT (blocking)."""

    if not speech_client or not audio_bytes:
        return None

    audio = speech.RecognitionAudio(content=audio_bytes)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code=LANGUAGE_CODE,
        enable_automatic_punctuation=True,
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


def listen(duration=5):
    """
    Simple blocking listen.
    Guaranteed to return text or FALLBACK_TEXT.
    """

    t0 = time.time()

    audio = record_audio(duration)
    text = speech_to_text(audio)

    elapsed = round(time.time() - t0, 2)

    if not text:
        log("STT", "-", "No speech detected (fallback)", elapsed)
        print("[STT] No speech detected.")
        return FALLBACK_TEXT

    log("STT", "-", f"Heard '{text}'", elapsed)
    print("[STT] Heard:", text)
    return text


# ================================================================
#  STREAMING STT (PRIMARY PATH)
# ================================================================
def listen_continuous():
    """
    Streaming STT with:
    - Google-managed end-of-speech
    - Hard timeout
    - Safe fallback
    """

    if not speech_client:
        return FALLBACK_TEXT

    audio_queue = queue.Queue()
    stop_event = threading.Event()
    transcript_parts = []

    # ------------------------------------------------------------
    # Audio callback
    # ------------------------------------------------------------
    def audio_callback(indata, frames, time_info, status):
        if status:
            print(status)
        audio_queue.put(bytes(indata))

    # ------------------------------------------------------------
    # Generator feeding Google
    # ------------------------------------------------------------
    def request_generator():
        while not stop_event.is_set():
            try:
                chunk = audio_queue.get(timeout=0.1)
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
            except queue.Empty:
                continue

    # ------------------------------------------------------------
    # Google response loop
    # ------------------------------------------------------------
    def response_loop(responses):
        try:
            for response in responses:
                if stop_event.is_set():
                    break

                if not response.results:
                    continue

                result = response.results[0]
                transcript = result.alternatives[0].transcript

                if result.is_final:
                    print(f"\n[STT] Confirmed: {transcript}")
                    transcript_parts.append(transcript)
                    stop_event.set()
                else:
                    print(f"[STT] Live: {transcript}", end="\r")

        except Exception as e:
            if not stop_event.is_set():
                print(f"[STT] Response Error: {e}")

    # ------------------------------------------------------------
    # Google config
    # ------------------------------------------------------------
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code=LANGUAGE_CODE,
        enable_automatic_punctuation=True,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True,
        single_utterance=True,  # CRITICAL
    )

    # ------------------------------------------------------------
    # Start streaming
    # ------------------------------------------------------------
    start_time = time.time()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=audio_callback,
    ):
        print("[STT] Listening...")

        responses = speech_client.streaming_recognize(
            config=streaming_config,
            requests=request_generator(),
        )

        t = threading.Thread(
            target=response_loop,
            args=(responses,),
            daemon=True,
        )
        t.start()

        # --------------------------------------------------------
        # HARD TIMEOUT WATCHDOG
        # --------------------------------------------------------
        while not stop_event.is_set():
            time.sleep(0.1)
            if time.time() - start_time > MAX_LISTEN_SECONDS:
                print("\n[STT] No speech detected (timeout).")
                stop_event.set()

        t.join(timeout=1.0)

    final_text = " ".join(transcript_parts).strip()

    if not final_text:
        log("STT", "-", "Fallback triggered (silence)", MAX_LISTEN_SECONDS)
        return FALLBACK_TEXT

    log("STT", "-", f"Heard '{final_text}'", round(time.time() - start_time, 2))
    return final_text
