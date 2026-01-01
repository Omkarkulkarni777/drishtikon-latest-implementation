import os
import queue
import threading
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
from google.cloud import speech

from core.config import init_stt
from core.constants import CHANNELS, SAMPLE_RATE
from core.utils import load_credential_path
from core.logger import log

LANGUAGE_CODE = "en-US"
LANGUAGE_CODE_IN = "en-IN"
SILENCE_THRESHOLD = 3.0
SILENCE_RMS_THRESHOLD = 500
TARGET_RMS = 2000
MIN_RMS = 100
BOOST_THRESHOLD = 500

class STTManager:
    def __init__(self):
        self.cred_path = load_credential_path("core", "stt-key.json")
        self.client = init_stt(self.cred_path)
        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._last_speech_time = time.time()

    def record_audio(self, duration=5, device=None):
        log("STT", "-", f"Recording {duration}s...")
        try:
            audio = sd.rec(
                int(duration * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                device=device
            )
            sd.wait()
            
            rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
            log("STT", "-", f"Recording complete. RMS: {rms:.0f}")
            
            if rms < MIN_RMS:
                log("STT", "-", "WARNING: Audio level very low")
            elif rms < BOOST_THRESHOLD:
                gain = TARGET_RMS / max(rms, 1)
                audio = np.clip(audio.astype(np.float32) * gain, -32768, 32767).astype(np.int16)
                log("STT", "-", f"Audio boosted by {gain:.1f}x")

            return audio.tobytes()
        except Exception as e:
            log("STT", "-", f"Microphone error: {e}")
            return None

    def speech_to_text(self, audio_bytes):
        if not self.client:
            log("STT", "-", "Client not initialized")
            return None

        try:
            debug_path = "/tmp/stt_debug.wav"
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            sf.write(debug_path, audio_array, SAMPLE_RATE)
        except Exception as e:
            log("STT", "-", f"Debug save failed: {e}")

        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLE_RATE,
            language_code=LANGUAGE_CODE,
            enable_automatic_punctuation=True,
            audio_channel_count=CHANNELS,
            model="command_and_search"
        )

        try:
            response = self.client.recognize(config=config, audio=audio)
            if not response.results:
                return None
            return response.results[0].alternatives[0].transcript
        except Exception as e:
            log("STT", "-", f"Google STT error: {e}")
            return None

    def listen(self, duration=5):
        t0 = time.time()
        audio_bytes = self.record_audio(duration)
        if not audio_bytes:
            return None
        
        text = self.speech_to_text(audio_bytes)
        t1 = time.time()
        log("STT", "-", f"Heard: '{text}'" if text else "No speech", t1 - t0)
        return text

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            log("STT", "-", f"Audio status: {status}")
        
        self._audio_queue.put(bytes(indata))
        
        rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
        if rms > SILENCE_RMS_THRESHOLD:
            self._last_speech_time = time.time()

    def _request_generator(self):
        while True:
            if self._stop_event.is_set():
                return
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
            except queue.Empty:
                continue

    def listen_continuous(self):
        if not self.client:
            log("STT", "-", "Client not initialized")
            return ""

        self._stop_event.clear()
        self._last_speech_time = time.time()
        full_transcript = []

        def response_loop(responses):
            try:
                for response in responses:
                    if self._stop_event.is_set():
                        break
                    if not response.results:
                        continue
                    
                    result = response.results[0]
                    transcript = result.alternatives[0].transcript
                    
                    if result.is_final:
                        log("STT", "-", f"Confirmed: {transcript}")
                        full_transcript.append(transcript)
            except Exception as e:
                if not self._stop_event.is_set():
                    log("STT", "-", f"Stream error: {e}")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._audio_callback,
        ):
            log("STT", "-", "Listening continuous...")
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=SAMPLE_RATE,
                language_code=LANGUAGE_CODE_IN,
                enable_automatic_punctuation=True,
                audio_channel_count=CHANNELS,
                model="command_and_search"
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=True,
            )

            responses = self.client.streaming_recognize(
                config=streaming_config,
                requests=self._request_generator(),
            )

            t = threading.Thread(target=response_loop, args=(responses,), daemon=True)
            t.start()

            while not self._stop_event.is_set():
                time.sleep(0.1)
                if time.time() - self._last_speech_time > SILENCE_THRESHOLD:
                    log("STT", "-", f"Silence detected ({SILENCE_THRESHOLD}s)")
                    self._stop_event.set()

            t.join(timeout=1.0)

        return " ".join(full_transcript)

_manager = STTManager()

def listen(duration=5):
    return _manager.listen(duration)

def listen_continuous():
    return _manager.listen_continuous()
