import os
import cv2
import io
import time
import threading
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai

from core.utils import absolute_path, ensure_dir, load_credential_path
from core.tts import speak
from core.tts_player import tts_main
from core.playback_controls import play, non_blocking_play, wait_for_key
from core.prompts import (
    select_file_p,
    generating_answer_p,
    exiting_detection_module_p
)

load_dotenv()

# ================================================================
#  GEMINI CONFIG
# ================================================================
load_credential_path("detection", "detect-key.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=GEMINI_API_KEY)

# ================================================================
#  GEMINI PROMPT (VERY IMPORTANT)
# ================================================================
GEMINI_SCENE_PROMPT = """
You are assisting a visually impaired user.

Describe only what requires attention right now.
Focus on obstacles, people, vehicles, or hazards.
Use at most four short sentences.
Be concise and calm.
"""

# ================================================================
#  GEMINI SCENE SUMMARY
# ================================================================
def gemini_scene_summary(image_path: str) -> str:
    img = Image.open(image_path)
    if img.mode == "RGBA":
        img = img.convert("RGB")

    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)

    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content([
        {"mime_type": "image/jpeg", "data": buf.getvalue()},
        GEMINI_SCENE_PROMPT
    ])

    return getattr(response, "text", "I could not understand the scene.")

# ================================================================
#  MAIN LOOP
# ================================================================
def main():
    ensure_dir(absolute_path("results", "gemini_cache"))

    play(tts_main, select_file_p)

    # ------------------------------------------------------------
    # Image selection
    # ------------------------------------------------------------
    root = tk.Tk()
    root.withdraw()
    img_path = filedialog.askopenfilename()
    root.destroy()

    cam = None
    if not img_path:
        cam = cv2.VideoCapture(0)

    print("\n[g] Describe scene | [q] Quit\n")

    while True:

        # --------------------------------------------------------
        # Wait for user intent
        # --------------------------------------------------------
        key = wait_for_key(valid_keys={"g", "q"})

        # --------------------------------------------------------
        # Gemini summary
        # --------------------------------------------------------
        if key == "g":
            # --------------------------------------------------------
            # Capture frame if camera is active
            # --------------------------------------------------------
            if cam:
                ret, frame = cam.read()
                if not ret:
                    break
                img_path = absolute_path("results", "gemini_cache", "live.jpg")

            play(tts_main, generating_answer_p)

            try:
                cv2.imwrite(img_path, frame)
                text = gemini_scene_summary(img_path)
                audio_path = speak(text)

                non_blocking_play(
                    tts_main,
                    audio_path,
                    cmd_to_stop_audio_file="Press 's' to stop description"
                )
            except Exception as e:
                print(f"[Gemini Error] {e}")

        # --------------------------------------------------------
        # Exit
        # --------------------------------------------------------
        elif key == "q":
            play(tts_main, exiting_detection_module_p)
            break

    if cam:
        cam.release()

# ================================================================
if __name__ == "__main__":
    main()
