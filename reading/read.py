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
import select
import tkinter as tk
from tkinter import filedialog
from PIL import Image
import io
from dotenv import load_dotenv
import google.generativeai as genai

from core.utils import absolute_path, ensure_dir, load_credential_path
from core.tts import speak, speak_blocking
from core.tts_player import tts_main, tts_summary, tts_prompt
from core.logger import log
from core.text_utils import split_into_sentences
from core.summarize import summarize

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
    """
    Resize + compress image for faster Gemini processing.
    """
    img = Image.open(image_path)

    if img.mode == "RGBA":
        img = img.convert("RGB")

    img.thumbnail((1800, 1800))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)

    return buf.getvalue()


# ================================================================
# GEMINI OCR
# ================================================================
def gemini_read(image_path, prompt):
    """
    Run Gemini OCR + prompt on the image.
    """
    if not GEMINI_API_KEY or not GEMINI_MODEL:
        return "Gemini not configured.", 0

    optimized_bytes = optimize_image(image_path)
    model = genai.GenerativeModel(GEMINI_MODEL)

    final_text = []
    start = time.time()

    response = model.generate_content(
        [
            {"mime_type": "image/jpeg", "data": optimized_bytes},
            prompt,
        ],
        stream=True,
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
            ("All Files", "*.*"),
        ],
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
        prompt_path = speak("Press SPACE to capture, ESC to exit.")
        if prompt_path:
            tts_main.play(prompt_path)

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
    prompt_path = speak("Switching to Raspberry Pi camera mode.")
    if prompt_path:
        tts_main.play(prompt_path)

    return capture_with_libcamera()


# ================================================================
# MAIN
# ================================================================
def main():
    ensure_results_dir()

    # Intro prompt
    speak_blocking("Select an image file. If you cancel, I will open the camera.")

    # STEP 1 — Select file
    img_path = choose_file()

    if not img_path:
        fallback_path = speak("No file selected. Opening camera.")
        if fallback_path:
            tts_main.play(fallback_path)

        img_path = capture_image()

    if not img_path:
        speak_blocking("No image captured. Exiting.")
        return

    # STEP 2 — OCR prompt
    process_path = speak_blocking("Processing the image. Please wait.")

    refinement_prompt = """
    This image was captured by a blind user.
    Extract the exact text from the book page.
    Do not paraphrase or modify anything.
    """

    text, duration = gemini_read(img_path, refinement_prompt)
    log("READING", img_path, f"{len(text)} chars", duration)

    print("\n===== OCR RESULT =====\n")
    print(text)
    print("\n=======================\n")

    # Handle empty OCR text edge case
    if not text.strip():
        empty_path = speak_blocking("The page appears empty or unreadable.")
        return

    # ================================================================
    # Chunk-based reading with pause + summary (Commit 8.8 polished)
    # ================================================================
    sentences = split_into_sentences(text)

    if not sentences:
        speak_blocking("I could not extract readable sentences from this page.")
        return

    print("\n===== CHUNKED READING (PAUSE + SUMMARY ENABLED) =====\n")

    read_so_far = []
    current_index = 0

    # -------------------------
    # MAIN CHUNK LOOP
    # -------------------------
    while current_index < len(sentences):

        sentence = sentences[current_index]
        print(f"[READ] {current_index+1}/{len(sentences)} → {sentence}")

        audio_path = speak(sentence)
        tts_main.play(audio_path)

        # -----------------------------
        # INNER PLAYBACK MONITOR LOOP
        # -----------------------------
        while True:

            # 1. Chunk finished naturally
            if not tts_main.is_playing():
                break

            # 2. Non-blocking key check
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.readline().strip().lower()

                # -------------------------
                # PAUSE MAIN READING
                # -------------------------
                if key == "p":
                    print("[PAUSE] Reading paused")
                    tts_main.pause()
                    speak_blocking("Reading paused")

                    # ==========================
                    # PAUSE MENU
                    # ==========================
                    while True:
                        print("\nPaused. Options:")
                        print("  r = resume reading")
                        print("  m = summarize what has been read so far")
                        print("  q = quit reading module")
                        sys.stdout.flush()

                        choice = sys.stdin.readline().strip().lower()

                        # -------------------------
                        # RESUME
                        # -------------------------
                        if choice == "r":
                            print("[RESUME] Continuing reading")
                            speak_blocking("Resuming reading")
                            time.sleep(1)
                            tts_main.resume()
                            break

                        # -------------------------
                        # QUIT
                        # -------------------------
                        elif choice == "q":
                            print("[QUIT] Exiting reading module.")
                            speak_blocking("Exiting reading module.")
                            tts_main.stop()
                            return

                        # -------------------------
                        # SUMMARY MODE
                        # -------------------------
                        elif choice == "m":
                            if not read_so_far:
                                print("[SUMMARY] No content has been read yet.")
                                speak_blocking("No content has been read yet.")
                                continue

                            print("[SUMMARY] Generating summary...")
                            speak_blocking("Generating summary...")

                            summary_input = " ".join(read_so_far)
                            summary_text = summarize(summary_input)

                            # handle empty summary (rare but could happen)
                            if not summary_text.strip():
                                print("[SUMMARY] Summary is empty.")
                                speak_blocking("Summary empty!")
                                continue

                            print("\n===== SUMMARY OUTPUT =====\n")
                            print(summary_text)
                            print("\n============================\n")

                            summary_audio = speak(summary_text)
                            tts_summary.play(summary_audio)

                            print("Summary Mode:")
                            print("  s = stop summary and return to pause menu")

                            # -------------------------
                            # SUMMARY MODE LOOP
                            # -------------------------
                            while True:
                                if not tts_summary.is_playing():
                                    print("[SUMMARY] Finished.")
                                    break

                                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                                    subkey = sys.stdin.readline().strip().lower()

                                    if subkey == "s":
                                        print("[SUMMARY] Summary stopped.")
                                        speak_blocking("Stopping summary")
                                        tts_summary.stop()
                                        break

                                time.sleep(0.05)

                            print("\nBack to pause menu...\n")
                            speak_blocking("Back to pause menu")

                        else:
                            print("Invalid option. Try again.")

                # -------------------------
                # MID-PLAYBACK RESUME
                # -------------------------
                elif key == "r":
                    print("[RESUME] Resuming playback")
                    speak_blocking("Resuming...")
                    time.sleep(1)
                    tts_main.resume()

                # -------------------------
                # FULL EXIT
                # -------------------------
                elif key == "q":
                    print("[QUIT] Stopping reading module")
                    speak_blocking("Stopping...")
                    tts_main.stop()
                    return

            time.sleep(0.05)

        # Finished this sentence
        read_so_far.append(sentence)
        current_index += 1

    print("\n===== COMPLETED ALL SENTENCES =====\n")
 
# ================================================================
if __name__ == "__main__":
    main()
