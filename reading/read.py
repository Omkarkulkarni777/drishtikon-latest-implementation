import os
import sys
import subprocess

# Ensure the project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import cv2
import time
import datetime
import tkinter as tk
from tkinter import filedialog
from PIL import Image
import io
from dotenv import load_dotenv
import google.generativeai as genai

from core.utils import absolute_path, ensure_dir, load_credential_path
from core.tts import speak
from core.logger import log

load_dotenv()

# ================================================================
#  CREDENTIALS
# ================================================================
CRED_PATH = load_credential_path("reading", "reading-key.json")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ================================================================
# HELPERS
# ================================================================
def ensure_results_dir():
    ensure_dir(absolute_path("results"))
    ensure_dir(absolute_path("results", "reading_outputs"))


# ================================================================
# IMAGE OPTIMIZATION
# ================================================================
def optimize_image(image_path):
    img = Image.open(image_path)

    if img.mode == "RGBA":
        img = img.convert("RGB")

    img.thumbnail((1800, 1800))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)

    return buf.getvalue()


# ================================================================
# GEMINI OCR + SUMMARIZATION
# ================================================================
def gemini_read(image_path, prompt):

    if not GEMINI_API_KEY or not GEMINI_MODEL:
        return "Gemini not configured.", 0

    optimized_bytes = optimize_image(image_path)
    model = genai.GenerativeModel(GEMINI_MODEL)

    final_text = []
    start = time.time()

    response = model.generate_content(
        [
            {"mime_type": "image/jpeg", "data": optimized_bytes},
            prompt
        ],
        stream=True
    )

    for chunk in response:
        if hasattr(chunk, "text") and chunk.text:
            final_text.append(chunk.text)

    duration = round(time.time() - start, 2)
    return "".join(final_text), duration


# ================================================================
# FILE PICKER
# ================================================================
def choose_file():
    root = tk.Tk()
    root.attributes("-topmost", True)
    root.withdraw()

    fp = filedialog.askopenfilename(
        title="Select an image file",
        filetypes=[
            ("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp"),
            ("All Files", "*.*")
        ]
    )
    root.destroy()

    if not fp:
        return None

    # Save copy to results
    img = cv2.imread(fp)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = absolute_path("results", "reading_outputs", f"capture_{ts}.jpg")
    cv2.imwrite(save_path, img)

    return save_path


# ================================================================
# CAMERA CAPTURE - Raspberry Pi compatible
# ================================================================
def capture_with_libcamera():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = absolute_path("results", "reading_outputs", f"capture_{ts}.jpg")

    cmd = ["libcamera-still", "-o", out_path, "--immediate", "--timeout", "1"]

    try:
        subprocess.run(cmd, check=True)
        return out_path
    except Exception:
        return None


def capture_image():
    # Try OpenCV camera first (legacy mode)
    cam = cv2.VideoCapture(0)

    if cam.isOpened():
        speak("Press SPACE to capture, ESC to exit.")

        while True:
            ret, frame = cam.read()
            if not ret:
                continue

            cv2.imshow("Camera Capture - Press SPACE", frame)
            key = cv2.waitKey(1)

            if key == 32:  # SPACE
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = absolute_path("results", "reading_outputs", f"capture_{ts}.jpg")
                cv2.imwrite(path, frame)
                cam.release()
                cv2.destroyAllWindows()
                return path

            elif key == 27:  # ESC
                break

        cam.release()
        cv2.destroyAllWindows()

    # If OpenCV fails → fallback to libcamera
    speak("Switching to Raspberry Pi camera mode.")
    return capture_with_libcamera()


# ================================================================
# MAIN
# ================================================================
def main():
    ensure_results_dir()
    speak("Select an image file. If you cancel, I will open the camera.")

    img_path = choose_file()

    if not img_path:
        speak("No file selected. Opening camera.")
        img_path = capture_image()

    if not img_path:
        speak("No image captured. Exiting.")
        return

    refinement_prompt = """
    This image was captured by a blind user.
    Extract the exact text from the book page.
    Do not paraphrase or modify anything.
    """

    speak("Processing the image. Please wait.")

    text, duration = gemini_read(img_path, refinement_prompt)
    log("READING", img_path, f"{len(text)} chars", duration)

    print("\n===== OCR RESULT =====\n")
    print(text)
    print("\n=======================\n")

    speak(text)


# ================================================================
if __name__ == "__main__":
    main()
