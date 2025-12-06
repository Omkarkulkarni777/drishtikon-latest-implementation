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
    # PRELOAD ALL CACHED PROMPTS (WAV)
    # ---------------------------------------------------------
    select_file_p = speak_cached(
        "Select an image file. If you cancel, I will open the camera.",
        "select_file.wav"
    )
    no_file_p = speak_cached(
        "No file selected. Opening camera.",
        "no_file_open_camera.wav"
    )
    no_image_exit_p = speak_cached(
        "No image captured. Exiting.",
        "no_image_exit.wav"
    )
    processing_p = speak_cached(
        "Processing the image. Please wait.",
        "processing_wait.wav"
    )
    empty_page_p = speak_cached(
        "The page appears empty or unreadable.",
        "empty_page.wav"
    )
    no_sentences_p = speak_cached(
        "I could not extract readable sentences from this page.",
        "no_sentences.wav"
    )
    no_content_yet_p = speak_cached(
        "No content has been read yet.",
        "no_content_yet.wav"
    )
    generating_summary_p = speak_cached(
        "Generating summary.",
        "generating_summary.wav"
    )
    stopping_summary_p = speak_cached(
        "Stopping summary.",
        "stopping_summary.wav"
    )
    back_pause_menu_p = speak_cached(
        "Back to pause menu.",
        "back_pause_menu.wav"
    )
    exiting_module_p = speak_cached(
        "Exiting reading module.",
        "exiting_module.wav"
    )
    vc_intro_p = speak_cached(
        "Voice control. Say summary, resume, or quit.",
        "voice_intro.wav"
    )
    vc_retry_p = speak_cached(
        "I did not catch that. Please try again.",
        "retry_voice.wav"
    )
    vc_unknown_p = speak_cached(
        "Unknown command. Please say summary, resume, or quit..",
        "unknown_command.wav"
    )
    vc_back_p = speak_cached(
        "Back to voice control.",
        "back_voice.wav"
    )
    return_to_reading_p = speak_cached(
        "Returning to reading.",
        "return_to_reading.wav"
    )
    all_done_p = speak_cached(
        "Completed all sentences.",
        "all_sentences_done.wav"
    )

    pause_beep = absolute_path("sounds", "pause_beep.wav")
    resume_beep = absolute_path("sounds", "resume_beep.wav")

    # ---------------------------------------------------------
    # INTRO PROMPT (critical)
    # ---------------------------------------------------------
    tts_main.stop()
    tts_summary.stop()
    tts_prompt.stop()
    time.sleep(1.0)
    tts_main.play(select_file_p)
    while tts_main.is_playing():
        time.sleep(0.05)
    # let ALSA settle before Tk launches
    time.sleep(1.0)

    # ---------------------------------------------------------
    # STEP 1 — Select file
    # ---------------------------------------------------------
    img_path = choose_file()

    if not img_path:
        # non-critical info
        tts_main.stop()
        tts_summary.stop()
        tts_prompt.stop()
        time.sleep(1.0)
        tts_main.play(no_file_p)
        while tts_main.is_playing():
            time.sleep(0.05)

        time.sleep(1.0)
        img_path = capture_image()

    if not img_path:
        tts_main.stop()
        tts_summary.stop()
        tts_prompt.stop()
        time.sleep(1.0)
        tts_main.play(no_image_exit_p)
        while tts_main.is_playing():
            time.sleep(0.05)
        return

    # ---------------------------------------------------------
    # OCR PROMPT
    # ---------------------------------------------------------
    tts_main.stop()
    tts_summary.stop()
    tts_prompt.stop()
    time.sleep(1.0)
    tts_main.play(processing_p)
    # IMPORTANT: do not do heavy work while this is playing
    while tts_main.is_playing():
        time.sleep(0.05)
    time.sleep(1.0)

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
        tts_main.stop()
        tts_summary.stop()
        tts_prompt.stop()
        time.sleep(1.0)
        tts_main.play(empty_page_p)
        while tts_main.is_playing():
            time.sleep(0.05)
        return

    # ---------------------------------------------------------
    # CHUNKING
    # ---------------------------------------------------------
    sentences = split_into_sentences(text)
    if not sentences:
        tts_main.stop()
        tts_summary.stop()
        tts_prompt.stop()
        time.sleep(1.0)
        tts_main.play(no_sentences_p)
        while tts_main.is_playing():
            time.sleep(0.05)
        return

    read_so_far = []
    current_index = 0

    print("\n===== CHUNKED READING (PAUSE + SUMMARY + VOICE MODE) =====\n")

    # ---------------------------------------------------------
    # CHUNK LOOP
    # ---------------------------------------------------------
    while current_index < len(sentences):
        sentence = sentences[current_index]
        print(f"[READ] {current_index + 1}/{len(sentences)} → {sentence}")

        sentence_audio = speak(sentence)

        tts_main.stop()
        tts_summary.stop()
        tts_prompt.stop()
        time.sleep(0.4)
        tts_main.play(sentence_audio)

        # -----------------------------
        # INNER PLAYBACK MONITOR LOOP
        # -----------------------------
        while True:
            if not tts_main.is_playing():
                break

            # Non-blocking key press
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.readline().strip().lower()

                # =====================================================
                # (p) — PAUSE (always restart chunk on resume)
                # =====================================================
                if key == "p":
                    tts_main.stop()
                    tts_summary.stop()
                    tts_prompt.stop()
                    time.sleep(1.0)

                    tts_prompt.play(pause_beep)
                    time.sleep(0.2)

                    # ----- PAUSE MENU -----
                    while True:
                        print("\nPaused. Options:")
                        print("  r = resume this part")
                        print("  m = summarize what has been read so far")
                        print("  q = quit reading module")
                        sys.stdout.flush()

                        choice = sys.stdin.readline().strip().lower()

                        # RESUME → restart sentence from start
                        if choice == "r":
                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_prompt.play(resume_beep)
                            time.sleep(0.2)

                            sentence_audio = speak(sentence)
                            tts_main.play(sentence_audio)
                            break

                        # SUMMARY
                        elif choice == "m":
                            if not read_so_far:
                                tts_main.stop()
                                tts_summary.stop()
                                tts_prompt.stop()
                                time.sleep(1.0)

                                tts_main.play(no_content_yet_p)
                                while tts_main.is_playing():
                                    time.sleep(0.05)
                                continue

                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_main.play(generating_summary_p)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            time.sleep(1.0)

                            summary_text = summarize(" ".join(read_so_far))
                            summary_audio = speak(summary_text)
                            print("\n========SUMMARY=======\n")
                            print(summary_text)

                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)
                            tts_summary.play(summary_audio)

                            print("Summary mode — press 's' to stop")

                            while True:
                                if not tts_summary.is_playing():
                                    break

                                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                                    if sys.stdin.readline().strip().lower() == "s":
                                        tts_main.stop()
                                        tts_summary.stop()
                                        tts_prompt.stop()
                                        time.sleep(1.0)

                                        tts_main.play(stopping_summary_p)
                                        while tts_main.is_playing():
                                            time.sleep(0.05)
                                        break

                                time.sleep(0.05)

                            # Back to pause menu with prompt
                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_main.play(back_pause_menu_p)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            continue

                        # QUIT
                        elif choice == "q":
                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_main.play(exiting_module_p)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            return

                        else:
                            print("Invalid option.")
                            continue

                # =====================================================
                # (v) — VOICE MODE
                # =====================================================
                elif key == "v":
                    from core.stt_commands import listen_for_command

                    tts_main.stop()
                    tts_summary.stop()
                    tts_prompt.stop()
                    time.sleep(1.0)

                    tts_main.play(vc_intro_p)
                    while tts_main.is_playing():
                        time.sleep(0.05)
                    time.sleep(1.0)

                    failures = 0
                    MAX_FAILURES = 1

                    while failures < MAX_FAILURES:
                        command = listen_for_command()

                        if command is None:
                            failures += 1

                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)
                        
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            time.sleep(1.0)
                            continue

                        # RESUME → restart sentence
                        if command == "resume":
                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_prompt.play(resume_beep)
                            time.sleep(0.2)

                            sentence_audio = speak(sentence)
                            tts_main.play(sentence_audio)
                            break

                        # QUIT
                        elif command == "quit":
                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_main.play(exiting_module_p)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            return

                        # SUMMARY
                        elif command == "summary":
                            if not read_so_far:
                                tts_main.stop()
                                tts_summary.stop()
                                tts_prompt.stop()
                                time.sleep(1.0)

                                tts_main.play(no_content_yet_p)
                                while tts_main.is_playing():
                                    time.sleep(0.05)
                                continue

                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_main.play(generating_summary_p)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            time.sleep(1.0)

                            summary_text = summarize(" ".join(read_so_far))
                            summary_audio = speak(summary_text)
                            print("\n========SUMMARY=======\n")
                            print(summary_text)

                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_summary.play(summary_audio)

                            print("Summary mode — press 's' to stop")

                            while True:
                                if not tts_summary.is_playing():
                                    break

                                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                                    if sys.stdin.readline().strip().lower() == "s":
                                        tts_main.stop()
                                        tts_summary.stop()
                                        tts_prompt.stop()
                                        time.sleep(1.0)

                                        tts_main.play(stopping_summary_p)
                                        while tts_main.is_playing():
                                            time.sleep(0.05)
                                        break

                                time.sleep(0.05)

                            # Back to voice control
                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_main.play(vc_back_p)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            time.sleep(1.0)
                            continue

                        else:
                            failures += 1

                            tts_main.stop()
                            tts_summary.stop()
                            tts_prompt.stop()
                            time.sleep(1.0)

                            tts_main.play(vc_unknown_p)
                            while tts_main.is_playing():
                                time.sleep(0.05)
                            time.sleep(1.0)

                    # Too many failures → auto-return to reading (restart chunk)
                    if failures >= MAX_FAILURES:
                        tts_main.stop()
                        tts_summary.stop()
                        tts_prompt.stop()
                        time.sleep(1.0)

                        tts_main.play(return_to_reading_p)
                        while tts_main.is_playing():
                            time.sleep(0.05)
                        time.sleep(1.0)

                        sentence_audio = speak(sentence)
                        tts_main.play(sentence_audio)

            time.sleep(0.05)

        # Finished this sentence
        read_so_far.append(sentence)
        current_index += 1

    # ---------------------------------------------------------
    # FINISHED
    # ---------------------------------------------------------
    tts_main.stop()
    tts_summary.stop()
    tts_prompt.stop()
    time.sleep(1.0)

    tts_main.play(all_done_p)
    while tts_main.is_playing():
        time.sleep(0.05)

    print("\n===== COMPLETED ALL SENTENCES =====\n")
# ================================================================
if __name__ == "__main__":
    main()
