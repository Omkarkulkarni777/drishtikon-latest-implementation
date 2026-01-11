import os
import cv2
import io
import time
import threading
import datetime
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai

from core.stt import listen_continuous
from core.stt_commands import helper_for_exit
from core.utils import absolute_path, ensure_dir, load_credential_path, timeit
from core.tts import speak, speak_cached
from core.tts_player import tts_main
from core.playback_controls import play, non_blocking_play
from core.prompts import (
    generating_answer_p,
    exiting_detection_module_p,
    ask_query_intro_p,
)

load_dotenv()

# --------------------------------------------------
# ROUTED BUTTON EVENT (NO GPIO)
# --------------------------------------------------
BUTTON_FILE = "/tmp/detection_button"


def poll_button_event():
    if os.path.exists(BUTTON_FILE):
        os.remove(BUTTON_FILE)
        return "v"
    return None


# ================================================================
# GEMINI CONFIG
# ================================================================
load_credential_path("detection", "detect-key.json")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=GEMINI_API_KEY)

# ================================================================
# GEMINI PROMPT
# ================================================================
GEMINI_SCENE_PROMPT = """
Answer in Marathi.
You are assisting a visually impaired user.
Describe only what requires attention right now.
Focus on obstacles, people, vehicles, or hazards.
Be concise and calm.
"""


# ================================================================
# GEMINI SCENE SUMMARY
# ================================================================
@timeit("[DETECTION GEMINI SCENE SUMMARY]")
def gemini_scene_summary(image_path: str, user_query: str | None = None) -> str:
    img = Image.open(image_path)

    if img.mode == "RGBA":
        img = img.convert("RGB")

    img.thumbnail((1600, 1600))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)

    prompt = user_query or GEMINI_SCENE_PROMPT
    prompt += (
        "\nIMAGE DOES NOT HAVE THE USER. "
        "IT IS TAKEN BY THE USER. "
        "IT IS NOT A SELFIE. "
        "DO NOT include formatting. "
        "LESS THAN 60 WORDS."
    )

    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        [
            {"mime_type": "image/jpeg", "data": buf.getvalue()},
            prompt,
        ]
    )

    return getattr(response, "text", "I could not understand the scene.")


# ================================================================
# CAMERA CAPTURE
# ================================================================
def capture_image() -> str:
    cam = cv2.VideoCapture(0)

    if not cam.isOpened():
        raise RuntimeError("Camera could not be opened")

    print("[v] Capture image")

    try:
        while True:
            key = poll_button_event()
            if key == "v":
                ret, frame = cam.read()
                if not ret:
                    raise RuntimeError("Failed to capture image")

                img_path = absolute_path(
                    "results",
                    "gemini_cache",
                    "live.jpg",
                )
                cv2.imwrite(img_path, frame)
                play(tts_main, ask_query_intro_p)
                return img_path

            time.sleep(0.05)

    finally:
        cam.release()


# ================================================================
# MAIN LOOP
# ================================================================
@timeit("[DETECTION MAIN]")
def main():
    ensure_dir(absolute_path("results", "gemini_cache"))

    try:
        while True:
            img_path = capture_image()

            user_query = listen_continuous()

            if helper_for_exit(user_query) == "q" or 0 < len(user_query.split()) < 2:
                play(tts_main, exiting_detection_module_p)
                return

            play(tts_main, generating_answer_p)

            text = gemini_scene_summary(img_path, user_query)
            audio_path = speak(text)

            non_blocking_play(
                tts_main,
                audio_path,
                module_name="detection",
                cmd_to_stop_audio_file="Press 's' to stop description",
            )

    except Exception as e:
        print(f"[Detection Error] {e}")


# ================================================================
if __name__ == "__main__":
    main()
