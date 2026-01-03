import os
from pathlib import Path
import sys
import subprocess
import cv2
import time
import datetime
import threading
import tkinter as tk
from tkinter import filedialog
from PIL import Image
import io
from dotenv import load_dotenv
import google.generativeai as genai

from core.config import init_gemini
from core.constants import RESULTS_DIR, AUDIO_DIR, PROMPT_CACHE_DIR, READING_INPUTS_DIR, SENTENCE_CACHE_DIR, SUMMARY_CACHE_DIR
from core.stt import listen_continuous
from core.utils import absolute_path, ensure_dir, load_credential_path, timeit
from core.tts import speak
from core.stt_commands import helper_for_exit, listen_for_command
from core.tts_player import tts_main
from core.logger import log
from core.text_utils import split_into_sentences
from core.llm_task import LLMTask
from core.llm_runner import run_llm_task
from core.summarize import summarize
from core.query import answer_query
from core.prompts import *
from core.state import *
from core.playback_controls import play, non_blocking_play, wait_for_key
from reading.rag import main_rag, upload_text_to_store, rag_query_voice

load_dotenv()

# --------------------------------------------------
# BUTTON EVENT BRIDGE (NO GPIO)
# --------------------------------------------------
BUTTON_FILE = "/tmp/reading_button"

def poll_button_event():
    if os.path.exists(BUTTON_FILE):
        os.remove(BUTTON_FILE)
        return "v"
    return None

# ================================================================
#  GOOGLE CREDENTIALS
# ================================================================
CRED_PATH = load_credential_path("reading", "reading-key.json")

# ================================================================
# GEMINI CONFIG
# ================================================================
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
init_gemini()


# ================================================================
# HELPERS
# ================================================================
def ensure_results_dir():
    ensure_dir(RESULTS_DIR)
    ensure_dir(READING_INPUTS_DIR)
    ensure_dir(AUDIO_DIR)
    ensure_dir(PROMPT_CACHE_DIR)
    ensure_dir(SENTENCE_CACHE_DIR)
    ensure_dir(SUMMARY_CACHE_DIR)


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
@timeit("[GEMINI READ]")
def gemini_read(image_path, prompt):
    """
    Run Gemini OCR + prompt on the image.
    """
    if not GEMINI_API_KEY or not GEMINI_MODEL:
        return "Gemini not configured.", 0
    
    optimized_bytes = optimize_image(image_path)
    model = genai.GenerativeModel(GEMINI_MODEL)
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
    save_path = absolute_path("results", "reading_inputs", f"capture_{ts}.jpg")
    
    if Path(fp).resolve().parent == Path(save_path).resolve().parent:
        return fp
        
    cv2.imwrite(save_path, img)
    return save_path


# ================================================================
# CAMERA CAPTURE - Raspberry Pi compatible
# ================================================================
def capture_with_libcamera():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = absolute_path("results", "reading_inputs", f"capture_{ts}.jpg")
    cmd = ["libcamera-still", "-o", out_path, "--immediate", "--timeout", "1"]
    
    try:
        subprocess.run(cmd, check=True)
        return out_path
    except Exception:
        return None


# ================================================================
# CAMERA CAPTURE
# ================================================================
def capture_image():
    # Try OpenCV camera first (legacy mode)
    cam = cv2.VideoCapture(0)
    if cam.isOpened():
        play(tts_main, cap_intro_p)
        while True:
            ret, frame = cam.read()
            if not ret:
                continue
            
            cv2.imshow("Camera Capture - Press SPACE", frame)
            key = listen_for_command(is_question=True)
            
            if "capture" in key:  # SPACE
                time.sleep(3)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = absolute_path("results", "reading_inputs", f"capture_{ts}.jpg")
                cv2.imwrite(path, frame)
                cam.release()
                cv2.destroyAllWindows()
                return path
            elif "escape" in key:  # ESC
                break
        
        cam.release()
        cv2.destroyAllWindows()
        
    # If OpenCV fails → fallback to libcamera
    play(tts_main, switch_to_rasp_p)
    return capture_with_libcamera()

# ================================================================
# CLEAR AUDIO DIRECTORY
# ================================================================
def clear_audio_dir():
    for file in os.listdir(AUDIO_DIR):
        os.remove(absolute_path(AUDIO_DIR, file))


# ================================================================
# MAIN
# ================================================================
@timeit("[MAIN]")
def main():
    FILLER_ARRAY = [filler_music, filler_music_summary, fractals]
    FILLER_INDEX = 0
    FILLER = FILLER_ARRAY[FILLER_INDEX]
    
    ensure_results_dir()
    clear_audio_dir()

    # ---------------------------------------------------------
    # CHECK FOR EXISTING READING STATE (resume_mode)
    # ---------------------------------------------------------
    state = load_state()
    resume_mode = False
    
    if state:
        # Ask if want to continue the previous reading task
        play(tts_main, resume_previous_task_p)
        print("\nPrevious reading task found.")
        print("Press 'y' to continue or any other key to start a new task.")
        
        choice = listen_for_command()
        if choice == "y":
            print("[STATE] Resuming saved reading task...")
            sentences = state["sentences"]
            current_index = state["current_index"]
            read_so_far = sentences[:current_index]
            resume_mode = True
        else:
            print("[STATE] Discarding saved task...")
            resume_mode = False

    # ---------------------------------------------------------
    # NEW TASK FLOW (file select + OCR + chunking)
    # ---------------------------------------------------------
    if not resume_mode:
        # CLEAR STATE
        clear_state()
        
        # INTRO
        play(tts_main, select_file_p)
        
        # STEP 1 — Select file
        img_path = choose_file()
        if not img_path:
            play(tts_main, no_file_p)
            img_path = capture_image()
            
        if not img_path:
            play(tts_main, no_image_exit_p)
            return

        # OCR PROMPT
        play(tts_main, processing_p)
        tts_main.play(filler_music)
        
        refinement_prompt = f"""
        MAKE SURE TO EXTRACT TEXT IN THE RIGHT ORDER.
        ADD A PREFIX "SENT_GRP" AFTER EVERY TWO SENTENCES.
        IF POEM, ADD PREFIX "SENT_GRP" AFTER EVERY TWO 'LINES'.
        If the image contains:
        Math Equations or Figures => ONLY EXPLAIN THE CONCEPT WITHOUT MATH CONSTRUCT.
        DO NOT say X subscript Y, SAY X of Y.
        DO NOT X superscript Y, SAY X raised to Y.
        Abbreviations => CONVERT TO FULL FORMS.
        Error screen or artifact => Explain error.
        Comic Book artifact => CONVERT into book style narration.
        Social media message text => CONVERT into book style narration.
        A lot of text => SUMMARIZE contextual elements in 20 WORDS, then include the complete, UNSUMMARIZED text content.
        Medical text => Issue alarms and include UNSUMMARIZED text.
        Little text => SUMMARIZE contextual elements along with text in 25 WORDS.
        No text => Say "NO TEXT FOUND." and SUMMARIZE the visual in 15 WORDS.
        DO NOT include asterisks, quotes, or any formatting.
        """
        
        task = LLMTask(
            gemini_read,
            img_path,
            refinement_prompt
        )

        result = run_llm_task(task)
        text = None
        duration = None
        
        if result:
            text, duration = result
            log("READING", img_path, f"{len(text)} chars", duration)
        else:
            main()

        # After OCR:
        def helper_upload_text_to_store(text):
            store_name = upload_text_to_store(text)
            if not store_name:
                print("\nCould not perform RAG query due to upload failure.")
        
        if not text:
            return
            
        threading.Thread(target=helper_upload_text_to_store, args=(text, ), daemon=True).start()
        
        print("\n===== OCR RESULT =====\n")
        print(text)
        print("\n=======================\n")

        sentences = split_into_sentences(text)
        sentences.append("THE END...")
        
        if not sentences:
            play(tts_main, no_sentences_p)
            return
            
        read_so_far = []
        current_index = 0

    # ---------------------------------------------------------
    # CHUNK LOOP (supports resume_mode)
    # ---------------------------------------------------------
    print("\n===== CHUNKED READING (PAUSE + SUMMARY + VOICE MODE) =====\n")
    if resume_mode:
        print(f"[RESUME] Continuing from sentence {current_index + 1} of {len(sentences)}")

    while current_index < len(sentences):
        sentence = sentences[current_index]
        print(f"[READ] {current_index + 1}/{len(sentences)} → {sentence}")
        
        audio_file_name = f"sentence_0{current_index}.wav" if current_index < 10 else f"sentence_{current_index}.wav"
        sentence_audio = speak_cached(sentence, absolute_path(SENTENCE_CACHE_DIR, audio_file_name))
        tts_main.play(sentence_audio)

        # -----------------------------
        # PLAYBACK MONITOR
        # -----------------------------
        while True:
            if not tts_main.is_playing():
                print("\n_________________________________\n")
                break
            
            if current_index + 1 == len(sentences):
                key = "v"
                current_index += 1
            else:
                # Non-blocking keypress
                key = None
                
            btn = poll_button_event()
            if btn:
                key = btn

            # =====================================================
            # (p) — PAUSE
            # =====================================================
            if key == "p":
                play(tts_main, pause_beep)
                
                # ----- PAUSE MENU -----
                while True:
                    print("\nPaused. Options:")
                    print(" p = resume this part")
                    print(" r = search")
                    print(" x = ask a query")
                    print(" m = summarize what has been read so far")
                    print(" q = quit reading module")
                    sys.stdout.flush()
                    
                    choice = wait_for_key()

                    # RESUME → restart sentence
                    if choice == "p":
                        play(tts_main, resume_beep)
                        sentence_audio = speak_cached(sentence_audio, absolute_path(SENTENCE_CACHE_DIR, audio_file_name))
                        print("[PATH]", sentence_audio)
                        tts_main.play(sentence_audio)
                        break
                    
                    # RAG SEARCH
                    elif choice == "r":
                        play(tts_main, ask_query_intro_p)
                        question = listen_continuous()
                        
                        if question is None or not question.strip() or helper_for_exit(question) == "q":
                            play(tts_main, back_pause_menu_p)
                            continue
                        
                        play(tts_main, generating_answer_p)
                        
                        task = LLMTask(
                            rag_query_voice,
                            question
                        )

                        answer = run_llm_task(task)
                        print("\n========RAG ANSWER=======\n")
                        print(answer)

                        if not answer or not answer.strip() or answer.startswith("RAG Query Error"):
                            play(tts_main, could_not_find_answer_p)
                            play(tts_main, back_pause_menu_p)
                            continue
                        
                        answer_audio = speak(answer)
                        non_blocking_play(tts_main, answer_audio, "Press 's' to stop response", stopping_response_p)
                        play(tts_main, back_pause_menu_p)
                        continue

                    # SUMMARY
                    elif choice == "m":
                        if not read_so_far:
                            play(tts_main, no_content_yet_p)
                            play(tts_main, back_pause_menu_p)
                            continue
                            
                        play(tts_main, generating_summary_p)
                        tts_main.play(filler_music_summary)
                        
                        summary_audio_file_name = f"summary_0{current_index}.wav" if current_index < 10 else f"summary_{current_index}.wav"
                        summary_text = "Cached"

                        if not os.path.exists(absolute_path(SUMMARY_CACHE_DIR, summary_audio_file_name)):
                            task = LLMTask(summarize, " ".join(read_so_far))
                            summary_text = run_llm_task(task)

                        print("\n========SUMMARY=======\n")
                        print(summary_text)
                        
                        if not summary_text or not summary_text.strip():
                            play(tts_main, back_pause_menu_p)
                            continue

                        summary_audio = speak_cached(summary_text, absolute_path(SUMMARY_CACHE_DIR, summary_audio_file_name))
                        non_blocking_play(tts_main, summary_audio, "Press 's' to stop summary", stopping_summary_p)
                        play(tts_main, back_pause_menu_p)
                        continue

                    # QUERY RESOLUTION
                    elif choice == "x":
                        play(tts_main, ask_query_intro_p)
                        question = listen_continuous()
                        
                        if question is None or not question.strip() or helper_for_exit(question) == "q":
                            play(tts_main, back_pause_menu_p)
                            continue

                        play(tts_main, generating_answer_p)
                        task = LLMTask(
                            answer_query,
                            " ".join(read_so_far),
                            question
                        )
                        answer = run_llm_task(task)

                        print("\n========ANSWER=======\n")
                        print(answer)

                        if not answer or not answer.strip():
                            play(tts_main, back_pause_menu_p)
                            continue
                        
                        answer_audio = speak(answer)
                        non_blocking_play(tts_main, answer_audio, "Press 's' to stop response", stopping_response_p)
                        play(tts_main, back_pause_menu_p)
                        continue
                    
                    # QUIT
                    elif choice == "q":
                        if sentences and 0 <= current_index < len(sentences):
                            task_state = {
                                "sentences": sentences,
                                "current_index": current_index,
                            }
                            save_state(task_state)
                        play(tts_main, exiting_reading_module_p)
                        return
                    else:
                        tts_main.play(FILLER)
                        FILLER_INDEX = (FILLER_INDEX + 1) % len(FILLER_ARRAY)
                        FILLER = FILLER_ARRAY[FILLER_INDEX]
                        print("Invalid option.")
                        continue

            # =====================================================
            # (v) — VOICE MODE
            # =====================================================
            elif key == "v":
                play(tts_main, pause_beep)
                play(tts_main, vc_intro_p)
                
                while True:
                    choice = listen_for_command()

                    if choice is None or choice == "p":
                        play(tts_main, resume_beep)
                        sentence_audio = speak_cached(sentence, absolute_path(SENTENCE_CACHE_DIR, audio_file_name))
                        print("[PATH]", sentence_audio)
                        tts_main.play(sentence_audio)
                        break

                    elif choice == "r":
                        from_main_controller = False
                        task = LLMTask(main_rag, from_main_controller)
                        answer = run_llm_task(task)
                        print("\n========RAG ANSWER=======\n")
                        print(answer)
                        play(tts_main, vc_back_p)

                    elif choice == "m":
                        if not read_so_far:
                            play(tts_main, no_content_yet_p)
                            continue
                            
                        play(tts_main, generating_summary_p)
                        summary_audio_file_name = f"summary_0{current_index}.wav" if current_index < 10 else f"summary_{current_index}.wav"
                        summary_text = "Cached"

                        if not os.path.exists(absolute_path(SUMMARY_CACHE_DIR, summary_audio_file_name)):
                            task = LLMTask(summarize, " ".join(read_so_far))
                            summary_text = run_llm_task(task)

                        print("\n========SUMMARY=======\n")
                        print(summary_text)

                        if not summary_text or not summary_text.strip():
                            play(tts_main, vc_back_p)
                            continue

                        summary_audio = speak_cached(summary_text, absolute_path(SUMMARY_CACHE_DIR, summary_audio_file_name))
                        non_blocking_play(tts_main, summary_audio, "Press 's' to stop summary", stopping_summary_p)
                        play(tts_main, vc_back_p)
                        continue

                    elif choice == "x":
                        play(tts_main, ask_query_intro_p)
                        question = listen_continuous()
                        
                        if question is None or not question.strip() or helper_for_exit(question) == "q":
                            play(tts_main, vc_back_p)
                            continue   

                        play(tts_main, generating_answer_p)
                        task = LLMTask(
                            answer_query,
                            " ".join(read_so_far),
                            question
                        )
                        answer = run_llm_task(task)

                        print("\n========ANSWER=======\n")
                        print(answer)

                        if not answer or not answer.strip():
                            play(tts_main, vc_back_p)
                            continue
                        
                        answer_audio = speak(answer)
                        non_blocking_play(tts_main, answer_audio, "Press 's' to stop response", stopping_response_p)
                        play(tts_main, vc_back_p)
                        continue  

                    elif choice == "q":
                        if sentences and 0 <= current_index < len(sentences):
                            task_state = {
                                "sentences": sentences,
                                "current_index": current_index,
                            }
                            save_state(task_state)
                        play(tts_main, exiting_reading_module_p)
                        return
                        
                    elif choice == "k":
                        with open("/tmp/stop.txt", "w"):
                            pass
                    else:
                        print("Invalid option.")
                        continue
            
            # =====================================================
            # (n) -> NEXT SENTENCE
            # =====================================================
            elif key == "n" and current_index < len(sentences) - 2:
                play(tts_main, pause_beep)
                continue

            # =====================================================
            # (l) -> PREVIOUS CHUNK
            # =====================================================
            elif key == "l" and (0 < current_index < len(sentences)):
                play(tts_main, pause_beep)
                current_index -= 2
                continue

            # =====================================================
            # (r) -> REPLAY CHUNK
            # =====================================================
            elif key == "r" and (0 <= current_index < len(sentences)):
                play(tts_main, pause_beep)
                current_index -= 1
                continue
            
            time.sleep(0.05)
        # Finished this sentence
        read_so_far.append(sentence)
        current_index += 1

    # ---------------------------------------------------------
    # ALL SENTENCES COMPLETE
    # ---------------------------------------------------------
    clear_state()
    play(tts_main, all_done_p)
    print("\n===== COMPLETED ALL SENTENCES =====\n")


# ================================================================
if __name__ == "__main__":
    main()
