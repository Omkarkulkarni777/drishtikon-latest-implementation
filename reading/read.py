import tkinter as tk
from tkinter import filedialog
from google.cloud import texttospeech, speech, vision
import google.generativeai as genai
from google.oauth2 import service_account
import cv2
import os
import sys
import time
import datetime
from dotenv import load_dotenv

############################################################
#                 LOAD ENVIRONMENT
############################################################
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
genai.configure(api_key=GEMINI_API_KEY)

############################################################
#                 GOOGLE CREDENTIALS
############################################################
STT_TTS_CREDENTIALS = service_account.Credentials.from_service_account_file(
    r"cred\imperial-glyph-448202-p6-d36e2b69bd92.json"
)
VISION_CREDENTIALS = service_account.Credentials.from_service_account_file(
    r"cred\vision-key.json"
)

############################################################
#                 DIRECTORIES
############################################################
RES = "results"
AUDIO_DIR = os.path.join(RES, "audio_outputs")
os.makedirs(AUDIO_DIR, exist_ok=True)

############################################################
#                 CLIENTS
############################################################
tts_client = texttospeech.TextToSpeechClient(credentials=STT_TTS_CREDENTIALS)
stt_client = speech.SpeechClient(credentials=STT_TTS_CREDENTIALS)
vision_client = vision.ImageAnnotatorClient(credentials=VISION_CREDENTIALS)


############################################################
#                 TEXT TO SPEECH (NO SUBPROCESS)
############################################################
def speak(text):
    """
    Convert text to speech and play it using pure Python.
    No subprocess, no external calls.
    """
    synthesis_input = texttospeech.SynthesisInput(text=text)

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

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    audio_path = os.path.join(AUDIO_DIR, f"tts_{ts}.wav")

    with open(audio_path, "wb") as out:
        out.write(response.audio_content)

    # Playback using Media.SoundPlayer through ctypes (no subprocess)
    try:
        import winsound
        winsound.PlaySound(audio_path, winsound.SND_FILENAME)
    except Exception:
        pass


############################################################
#                 SPEECH INPUT (DISCONNECTED)
############################################################
def listen():
    """Placeholder STT function — currently returns None (intentionally)."""
    return None


############################################################
#               GOOGLE VISION OCR
############################################################
def extract_text_with_google_vision(image_bgr):
    """Runs Google Cloud Vision OCR on a BGR OpenCV image."""
    success, encoded_image = cv2.imencode(".jpg", image_bgr)
    if not success:
        return ""

    image = vision.Image(content=encoded_image.tobytes())
    response = vision_client.text_detection(image=image)

    if response.error.message:
        print("Google Vision OCR Error:", response.error.message)
        return ""

    annotations = response.text_annotations
    return annotations[0].description if annotations else ""


############################################################
#              GEMINI MULTIMODAL CORRECTION
############################################################
def refine_text_with_gemini_and_image(prompt_text, image_path):
    """Sends both text + image to Gemini for enhanced correction."""
    if not GEMINI_API_KEY or not GEMINI_MODEL:
        print("Gemini not configured. Returning raw text.")
        return prompt_text

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    except Exception as e:
        print("Could not read image for Gemini:", e)
        return prompt_text

    mime_type = get_mime_type(image_path)

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)

        res = model.generate_content([
            {"mime_type": mime_type, "data": image_bytes},
            prompt_text,
        ])

        text = getattr(res, "text", None)
        return text or prompt_text

    except Exception as err:
        print("Gemini error:", err)
        return prompt_text


def get_mime_type(path):
    ext = path.lower().split(".")[-1]
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }
    return mapping.get(ext, "image/jpeg")


############################################################
#               FILE CHOOSER (GUI)
############################################################
def choose_file():
    root = tk.Tk()
    root.withdraw()
    filepath = filedialog.askopenfilename(
        initialdir="images",
        title="Select an image file",
        filetypes=(
            ("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp"),
            ("All files", "*.*"),
        ),
    )
    root.destroy()
    return filepath


############################################################
#                IMAGE CAPTURE
############################################################
def capture_image_on_space():
    """
    Opens webcam feed and captures a single frame on SPACE.
    """
    cam = cv2.VideoCapture(0)

    if not cam.isOpened():
        speak("Camera not found.")
        return None, None

    img_counter = 0
    temp_image_path = None

    while True:
        ret, frame = cam.read()
        if not ret:
            speak("Camera disconnected.")
            break

        cv2.imshow("Press SPACE to capture, Q to quit", frame)
        k = cv2.waitKey(1)

        if k == 32:  # SPACE
            temp_image_path = f"captured_{img_counter}.png"
            cv2.imwrite(temp_image_path, frame)
            break

        elif k == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()

    return temp_image_path, frame


############################################################
#                      MAIN LOGIC
############################################################
def main():
    """
    This version is dedicated to Vision + Gemini ONLY.
    No subprocess calls.
    """
    speak("Welcome! This module handles reading text and refining content.")

    response = listen() or "read"

    if "read" in response:
        speak("Place the material in front of the camera and say 'click a picture'.")

        while True:
            command = listen() or "click a picture"

            if "click" in command:
                img_path, frame = capture_image_on_space()

                if not img_path:
                    continue
                # vision_time_start = time.time()
                # raw_text = extract_text_with_google_vision(frame) or "No text detected"
                # print(raw_text)
                # vision_time_end = time.time()
                # print(f"Time taken by Google Vision API: {vision_time_end - vision_time_start}")

                refinement_prompt = f"""
                    Task: Act as a better version of the Google Vision OCR.
                    If the image contains text (like from a book), include the complete, UNSUMMARIZED text content. 
                    Integrate all verified Vision detections and describe the content.
                    Summarize only contextual elements like book title, chapter, or page numbers separately from the quoted text. 
                    If the content is medical, issue a clear alarm. If no text is found, say "NO TEXT FOUND" and SUMMARIZE the visual (25 WORDS ONLY).
                    Do NOT use headers, bullet points, or lists in your final response.
                    """
                gemini_time_start = time.time()
                refined = refine_text_with_gemini_and_image(refinement_prompt, img_path)
                gemini_time_end = time.time()
                print(f"Time taken by Gemini API: {gemini_time_end - gemini_time_start}")

                speak(refined)
                print("Refined OCR result:")
                print(refined)

                os.remove(img_path)
                break

            else:
                speak("Say 'click a picture' when ready.")

    else:
        speak("This module now supports only OCR + Gemini refinement.")


############################################################
if __name__ == "__main__":
    main()
