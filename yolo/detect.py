import cv2
import time
import threading
import os
from ultralytics import YOLO
import simpleaudio as sa
import tkinter as tk
from tkinter import filedialog

from google.cloud import texttospeech
from google.oauth2 import service_account
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

############################################################
#                      CONFIG
############################################################

# --- GEMINI CONFIG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- GOOGLE TTS ---
TTS_CREDENTIALS = service_account.Credentials.from_service_account_file(
    "cred/imperial-glyph-448202-p6-d36e2b69bd92.json"
)
tts_client = texttospeech.TextToSpeechClient(credentials=TTS_CREDENTIALS)


############################################################
#                      TEXT TO SPEECH
############################################################

def speak(message):
    print("Speaking:", message)

    synthesis_input = texttospeech.SynthesisInput(text=message)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )

    temp_audio = "temp_tts.wav"
    with open(temp_audio, "wb") as f:
        f.write(response.audio_content)

    try:
        wave_obj = sa.WaveObject.from_wave_file(temp_audio)
        play = wave_obj.play()
        play.wait_done()
    except:
        pass

    try:
        os.remove(temp_audio)
    except:
        pass


############################################################
#                  FILE CHOOSER
############################################################

def choose_file():
    root = tk.Tk()
    root.withdraw()
    fp = filedialog.askopenfilename(
        title="Choose an image",
        filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
    )
    root.destroy()
    return fp


############################################################
#                  YOLO HELPERS
############################################################

model = YOLO("yolov8n.pt")

def describe_yolo(boxes, names):
    if not boxes:
        return "I do not see any objects."

    counts = {}
    for cls_idx in boxes:
        label = names[int(cls_idx)]
        counts[label] = counts.get(label, 0) + 1

    parts = []
    for label, count in counts.items():
        if count == 1:
            parts.append(f"a {label}")
        else:
            parts.append(f"{count} {label}s")

    return "I can see " + ", ".join(parts) + "."


############################################################
#                  GEMINI SCENE
############################################################

def gemini_scene(path):
    img = cv2.imread(path)
    success, encoded = cv2.imencode(".jpg", img)
    if not success:
        speak("Image encoding failed.")
        return

    image_bytes = encoded.tobytes()

    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = "Describe the scene in 40 words."

    res = model.generate_content(
        [{"mime_type": "image/jpeg", "data": image_bytes}, prompt]
    )

    text = getattr(res, "text", "")
    speak("Gemini summary: " + text)


############################################################
#                       MAIN
############################################################

def main():
    speak("Choose an image for object detection or analysis.")

    fp = choose_file()
    if not fp:
        speak("No image selected.")
        return

    img = cv2.imread(fp)

    # YOLO
    results = model.predict(img, verbose=False)
    annotated = results[0].plot()
    classes = [box.cls[0] for box in results[0].boxes]
    desc = describe_yolo(classes, results[0].names)

    speak("YOLO result: " + desc)

    cv2.imshow("YOLO Annotated", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # Gemini
    if GEMINI_API_KEY:
        gemini_scene(fp)


if __name__ == "__main__":
    main()
