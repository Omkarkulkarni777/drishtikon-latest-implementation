import datetime
import sys
import os

# Ensure project root in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
import threading
import cv2
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv
import google.generativeai as genai
from ultralytics import YOLO

from core.tts import speak
from core.logger import log
from core.utils import absolute_path, ensure_dir, load_credential_path

load_dotenv()

# ================================================================
# CREDENTIALS
# ================================================================
CRED_PATH = load_credential_path("yolo", "yolo-key.json")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ================================================================
# DIRECTORIES
# ================================================================
OUTPUT_DIR = absolute_path("results", "yolo_outputs")
ensure_dir(OUTPUT_DIR)

# ================================================================
# YOLO MODEL
# ================================================================
model = YOLO("yolov8n.pt")

# ================================================================
# FILE PICKER
# ================================================================
def choose_file():
    root = tk.Tk()
    root.attributes("-topmost", True)
    root.withdraw()

    fp = filedialog.askopenfilename(
        title="Select an image",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ("All Files", "*.*")]
    )
    root.destroy()
    return fp

# ================================================================
# YOLO COUNTS
# ================================================================
def describe_yolo(classes, names):
    if not classes:
        return "I do not see any objects."

    counts = {}
    for cls_idx in classes:
        label = names[int(cls_idx)]
        counts[label] = counts.get(label, 0) + 1

    parts = [f"{count} {label}{'' if count==1 else 's'}" for label, count in counts.items()]
    return "I can see " + ", ".join(parts) + "."

# ================================================================
# YOLO POSITIONAL DESCRIPTIONS
# ================================================================
def positional_descriptions(results):
    if len(results[0].boxes) == 0:
        return "I do not see any objects."

    boxes = results[0].boxes
    names = results[0].names
    width = results[0].orig_shape[1]

    left_items, center_items, right_items = [], [], []

    for box in boxes:
        cls_idx = int(box.cls[0])
        label = names[cls_idx]

        xyxy = box.xyxy[0]
        x_center = float((xyxy[0] + xyxy[2]) / 2)

        if x_center < width * 0.33:
            left_items.append(label)
        elif x_center > width * 0.66:
            right_items.append(label)
        else:
            center_items.append(label)

    parts = []
    if left_items:   parts.append("to the left I can see " + ", ".join(left_items))
    if center_items: parts.append("in the center there is " + ", ".join(center_items))
    if right_items:  parts.append("to the right I can see " + ", ".join(right_items))

    return ". ".join(parts) + "."

# ================================================================
# GEMINI SCENE DESCRIPTION
# ================================================================
def gemini_scene(path):
    img = cv2.imread(path)
    if img is None:
        speak("Image load failed.")
        return

    success, encoded = cv2.imencode(".jpg", img)
    if not success:
        speak("Image encoding failed.")
        return

    image_bytes = encoded.tobytes()
    model_g = genai.GenerativeModel(GEMINI_MODEL)

    prompt = "Describe the scene in 40 words."

    t0 = time.time()
    try:
        res = model_g.generate_content(
            [{"mime_type": "image/jpeg", "data": image_bytes}, prompt]
        )

        text = getattr(res, "text", "")
        duration = round(time.time() - t0, 2)

        speak("Gemini summary: " + text)
        log("YOLO-GEMINI", path, f"{len(text)} chars", duration)

    except Exception as e:
        log("YOLO-GEMINI", path, f"ERROR: {e}")

# ================================================================
# MAIN
# ================================================================
def main():
    speak("Select an image for detection.")
    fp = choose_file()

    if not fp:
        speak("No image selected.")
        return

    img = cv2.imread(fp)
    if img is None:
        speak("Failed to open image.")
        return

    # Window sizing for Pi screen
    h, w, _ = img.shape
    cv2.namedWindow("YOLO", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("YOLO", 900, int(h * 900 / w))

    speak("Press Y for YOLO detection, G for Gemini summary, Q to exit.")

    display_frame = img

    while True:
        cv2.imshow("YOLO", display_frame)
        key = cv2.waitKey(1) & 0xFF

        # EXIT
        if key == ord('q'):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = absolute_path("results", "yolo_outputs", f"output_{ts}.jpg")
            cv2.imwrite(save_path, img)
            speak("Exiting YOLO module.")
            break

        # YOLO DETECTION
        if key == ord('y'):
            t0 = time.time()

            results = model.predict(img, verbose=False)

            # YOLO returns RGB → convert to BGR for cv2
            annotated = results[0].plot()
            annotated_bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)
            display_frame = annotated_bgr

            classes = [box.cls[0] for box in results[0].boxes] if results[0].boxes else []
            desc = describe_yolo(classes, results[0].names)
            pos_desc = positional_descriptions(results)

            duration = round(time.time() - t0, 2)
            log("YOLO", fp, f"{desc} | {pos_desc}", duration)

            speak(desc + " " + pos_desc)

        # GEMINI SUMMARY
        if key == ord('g'):
            threading.Thread(
                target=gemini_scene,
                args=(fp,),
                daemon=True
            ).start()

    cv2.destroyAllWindows()

# ================================================================
if __name__ == "__main__":
    main()
