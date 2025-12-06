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
from core.tts import speak, speak_blocking, speak_cached
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
    ensure_dir(absolute_path("results", "prompt_cache"))


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
        ]
    )

    text = getattr(response, "text", "")
    duration = round(time.time() - start, 2)
    return text, duration


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

    # ---------------------------------------------------------
    # INTRO PROMPT (critical) → tts_main
    # ---------------------------------------------------------
    intro_audio = speak_cached(
        "Select an image file. If you cancel, I will open the camera.",
        "select_file.wav"
    )
    tts_main.play(intro_audio)
    while tts_main.is_playing():
        time.sleep(0.05)

    # STEP 1 — Select file
    img_path = choose_file()

    if not img_path:
        # Non-critical (should not interrupt future reading)
        no_file_audio = speak_cached(
            "No file selected. Opening camera.",
            "no_file_open_camera.wav"
        )
        tts_prompt.play(no_file_audio)

        img_path = capture_image()

    if not img_path:
        exit_audio = speak_cached(
            "No image captured. Exiting.",
            "no_image_exit.wav"
        )
        tts_main.play(exit_audio)
        while tts_main.is_playing():
            time.sleep(0.05)
        return

    # ---------------------------------------------------------
    # OCR PROMPT (non-critical)
    # ---------------------------------------------------------
    processing_audio = speak_cached(
        "Processing the image. Please wait.",
        "processing_wait.wav"
    )
    tts_prompt.play(processing_audio)

    refinement_prompt = """
    This image was captured by a blind user.
    Extract the exact text from the book page.
    Do not paraphrase or modify anything.
    Do not add asterisks or other formatting.
    """

    text, duration = gemini_read(img_path, refinement_prompt)
    log("READING", img_path, f"{len(text)} chars", duration)

    print("\n===== OCR RESULT =====\n")
    print(text)
    print("\n=======================\n")

    if not text.strip():
        empty_audio = speak_cached(
            "The page appears empty or unreadable.",
            "empty_page.wav"
        )
        tts_main.play(empty_audio)
        while tts_main.is_playing():
            time.sleep(0.05)
        return

    # -------- Chunking --------
    sentences = split_into_sentences(text)
    if not sentences:
        no_sentences_audio = speak_cached(
            "I could not extract readable sentences from this page.",
            "no_sentences.wav"
        )
        tts_main.play(no_sentences_audio)
        while tts_main.is_playing():
            time.sleep(0.05)
        return

    print("\n===== CHUNKED READING (PAUSE + SUMMARY + VOICE MODE) =====\n")

    read_so_far = []
    current_index = 0

    pause_beep = absolute_path("sounds", "pause_beep.wav")
    resume_beep = absolute_path("sounds", "resume_beep.wav")

    # -------------------------
    # MAIN CHUNK LOOP
    # -------------------------
    while current_index < len(sentences):

        sentence = sentences[current_index]
        print(f"[READ] {current_index + 1}/{len(sentences)} → {sentence}")

        # Generate + play sentence audio
        sentence_audio = speak(sentence)
        tts_main.play(sentence_audio)

        # -----------------------------
        # INNER PLAYBACK MONITOR LOOP
        # -----------------------------
        while True:

            # Natural end of chunk
            if not tts_main.is_playing():
                break

            # Non-blocking key check
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.readline().strip().lower()

                # =====================================================
                # PAUSE ("p") — restart chunk on resume
                # =====================================================
                if key == "p":
                    tts_main.stop()
                    tts_prompt.play(pause_beep)

                    # ----- PAUSE MENU -----
                    while True:
                        print("\nPaused. Options:")
                        print("  r = resume this part")
                        print("  m = summarize what has been read so far")
                        print("  q = quit reading module")
                        sys.stdout.flush()

                        choice = sys.stdin.readline().strip().lower()

                        # RESUME → restart the current sentence
                        if choice == "r":
                            tts_prompt.play(resume_beep)
                            sentence_audio = speak(sentence)
                            tts_main.play(sentence_audio)
                            break

                        # SUMMARY
                        elif choice == "m":
                            if not read_so_far:
                                no_content_audio = speak_cached(
                                    "No content has been read yet.",
                                    "no_content_yet.wav"
                                )
                                tts_main.play(no_content_audio)
                                while tts_main.is_playing():
                                    time.sleep(0.05)
                                continue

                            generating_summary_audio = speak_cached(
                                "Generating summary.",
                                "generating_summary.wav"
                            )
                            tts_prompt.play(generating_summary_audio)

                            summary_text = summarize(" ".join(read_so_far))
                            summary_audio = speak(summary_text)
                            tts_summary.play(summary_audio)

                            print("Summary mode — press 's' to stop")

                            while True:
                                if not tts_summary.is_playing():
                                    break

                                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                                    if sys.stdin.readline().strip().lower() == "s":
                                        stopping_audio = speak_cached(
                                            "Stopping summary.",
                                            "stopping_summary.wav"
                                        )
                                        tts_prompt.play(stopping_audio)
                                        tts_summary.stop()
                                        break

                                time.sleep(0.05)

                            continue  # back to pause menu

                        # QUIT
                        elif choice == "q":
                            exit_audio = speak_cached(
                                "Exiting reading module.",
                                "exiting_module.wav"
                            )
                            tts_main.play(exit_audio)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            tts_main.stop()
                            return

                        else:
                            print("Invalid option.")
                            continue

                # =====================================================
                # VOICE CONTROL ("v")
                # =====================================================
                elif key == "v":
                    from core.stt_commands import listen_for_command

                    tts_main.stop()
                    voice_intro_audio = speak_cached(
                        "Voice control. Say resume, summary, or quit.",
                        "voice_intro.wav"
                    )
                    tts_prompt.play(voice_intro_audio)

                    failures = 0
                    MAX_FAILURES = 5

                    while failures < MAX_FAILURES:
                        command = listen_for_command()

                        if command is None:
                            failures += 1
                            retry_audio = speak_cached(
                                "I did not catch that. Please try again.",
                                "retry_voice.wav"
                            )
                            tts_prompt.play(retry_audio)
                            continue

                        # RESUME → restart chunk
                        if command == "resume":
                            tts_prompt.play(resume_beep)
                            sentence_audio = speak(sentence)
                            tts_main.play(sentence_audio)
                            break

                        # QUIT
                        elif command == "quit":
                            exit_audio = speak_cached(
                                "Exiting reading module.",
                                "exiting_module.wav"
                            )
                            tts_main.play(exit_audio)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            tts_main.stop()
                            return

                        # SUMMARY
                        elif command == "summary":
                            if not read_so_far:
                                no_read_audio = speak_cached(
                                    "No content has been read yet.",
                                    "no_content_yet.wav"
                                )
                                tts_main.play(no_read_audio)
                                while tts_main.is_playing():
                                    time.sleep(0.05)
                                continue

                            generating_summary_audio = speak_cached(
                                "Generating summary.",
                                "generating_summary.wav"
                            )
                            tts_prompt.play(generating_summary_audio)

                            summary_text = summarize(" ".join(read_so_far))
                            summary_audio = speak(summary_text)
                            tts_summary.play(summary_audio)

                            print("Summary mode — press 's' to stop")

                            while True:
                                if not tts_summary.is_playing():
                                    break

                                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                                    if sys.stdin.readline().strip().lower() == "s":
                                        stopping_audio = speak_cached(
                                            "Stopping summary.",
                                            "stopping_summary.wav"
                                        )
                                        tts_prompt.play(stopping_audio)
                                        tts_summary.stop()
                                        break

                                time.sleep(0.05)

                            # back to voice control
                            back_voice_audio = speak_cached(
                                "Back to voice control.",
                                "back_voice.wav"
                            )
                            tts_prompt.play(back_voice_audio)
                            continue

                        else:
                            failures += 1
                            unknown_audio = speak_cached(
                                "Unknown command. Please say resume, summary, or quit.",
                                "unknown_command.wav"
                            )
                            tts_prompt.play(unknown_audio)

                    if failures >= MAX_FAILURES:
                        return_audio = speak_cached(
                            "Returning to reading.",
                            "return_to_reading.wav"
                        )
                        tts_prompt.play(return_audio)
                        sentence_audio = speak(sentence)
                        tts_main.play(sentence_audio)

            time.sleep(0.05)

        # Finished this sentence fully
        read_so_far.append(sentence)
        current_index += 1

    done_audio = speak_cached(
        "Completed all sentences.",
        "all_sentences_done.wav"
    )
    tts_main.play(done_audio)
    while tts_main.is_playing():
        time.sleep(0.05)

    print("\n===== COMPLETED ALL SENTENCES =====\n")
# ================================================================
if __name__ == "__main__":
    main()
