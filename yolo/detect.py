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

# COOLDOWN SETTINGS
ENV_UPDATE_INTERVAL = 60  # seconds
last_gemini_time = 0
gemini_busy = False

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

# =============================================
# POSITIONAL INFORMATION ASSISTANCE
# =============================================

def positional_descriptions(results):
    """
    Returns a description of object positions:
    left / center / right in the image.
    """

    if len(results[0].boxes) == 0:
        return "I do not see any objects."

    boxes = results[0].boxes
    names = results[0].names
    width = results[0].orig_shape[1]

    left_items = []
    center_items = []
    right_items = []

    for box in boxes:
        cls_idx = int(box.cls[0])
        label = names[cls_idx]

        xyxy = box.xyxy[0]  # [x1, y1, x2, y2]
        x_center = float((xyxy[0] + xyxy[2]) / 2)

        # LEFT
        if x_center < width * 0.33:
            left_items.append(label)

        # RIGHT
        elif x_center > width * 0.66:
            right_items.append(label)

        # CENTER
        else:
            center_items.append(label)

    parts = []

    if left_items:
        parts.append("to the left I can see " + ", ".join(left_items))

    if center_items:
        parts.append("in the center there is " + ", ".join(center_items))

    if right_items:
        parts.append("to the right I can see " + ", ".join(right_items))

    return ". ".join(parts) + "."

############################################################
#                  GEMINI SCENE
############################################################

def gemini_scene(path):
    global gemini_busy
    gemini_busy = True

    img = cv2.imread(path)
    success, encoded = cv2.imencode(".jpg", img)
    if not success:
        speak("Image encoding failed.")
        gemini_busy = False
        return
        
    gemini_start_time = time.time()
    image_bytes = encoded.tobytes()

    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = "Describe the scene in 40 words."

    try:
        res = model.generate_content(
            [{"mime_type": "image/jpeg", "data": image_bytes}, prompt]
        )
        gemini_end_time = time.time()
        print("Time taken by Gemini:", gemini_end_time - gemini_start_time)
        text = getattr(res, "text", "")
        speak("Gemini summary: " + text)
    except Exception as e:
        print("Gemini ERROR:", e)

    gemini_busy = False


############################################################
#                       MAIN
############################################################

def main():
    global last_gemini_time

    speak("Choose an image. Press Y for YOLO, G for Gemini, Q to quit.")

    fp = choose_file()
    if not fp:
        speak("No image selected.")
        return

    img = cv2.imread(fp)
    height, width, channels = img.shape
    while True:
        # Display (non-blocking)
        cv2.namedWindow("AI Vision", cv2.WINDOW_NORMAL)
        
        cv2.resizeWindow("AI Vision", 800, int(height * 800 / width))
        cv2.imshow("AI Vision", img)
        key = cv2.waitKey(1) & 0xFF

        # Quit
        if key == ord('q'):
            speak("Exiting vision module.")
            break

        # YOLO
        if key == ord('y'):
            yolo_start_time = time.time()
            results = model.predict(img, verbose=False)
            annotated = results[0].plot()

            # Convert RGB → BGR for OpenCV
            annotated_bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)

            # Old description (object counts)
            desc = describe_yolo([box.cls[0] for box in results[0].boxes], results[0].names)

            # NEW positional description
            pos_desc = positional_descriptions(results)
            yolo_end_time = time.time()
            print("Time taken by YOLO + positional information extraction:", yolo_end_time - yolo_start_time)
            speak("YOLO result: " + desc + ". " + pos_desc)

            cv2.imshow("AI Vision", annotated_bgr)
            
        # GEMINI
        if key == ord('g'):
            now = time.time()
            cooldown = now - last_gemini_time

            if gemini_busy:
                print("Gemini is busy…")
                continue

            if cooldown < ENV_UPDATE_INTERVAL:
                left = ENV_UPDATE_INTERVAL - cooldown
                speak(f"Gemini cooling down. {int(left)} seconds remaining.")
                continue

            last_gemini_time = now
            threading.Thread(
                target=gemini_scene,
                args=(fp,),
                daemon=True
            ).start()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
