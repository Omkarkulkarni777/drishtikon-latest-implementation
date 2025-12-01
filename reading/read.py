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
import simpleaudio as sa
from dotenv import load_dotenv
import time

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
    "cred/imperial-glyph-448202-p6-d36e2b69bd92.json"
)
VISION_CREDENTIALS = service_account.Credentials.from_service_account_file(
    "cred/vision-key.json"
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
#                 TEXT TO SPEECH (LINUX+RPi SAFE)
############################################################
def speak(text):
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

    try:
        wave_obj = sa.WaveObject.from_wave_file(audio_path)
        play_obj = wave_obj.play()
        play_obj.wait_done()
    except Exception as e:
        print("Audio playback error:", e)


############################################################
#               FILE CHOOSER (NO CAMERA)
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
#               GOOGLE VISION OCR
############################################################
def extract_text_with_google_vision(image_path):
    img = cv2.imread(image_path)
    success, encoded_image = cv2.imencode(".jpg", img)
    if not success:
        return ""
        
    vision_start_time = time.time()
    image = vision.Image(content=encoded_image.tobytes())
    response = vision_client.text_detection(image=image)
    vision_end_time = time.time()
    print("Time taken by Google Vision:", vision_end_time - vision_start_time)

    if response.error.message:
        print("Google Vision OCR Error:", response.error.message)
        return ""

    annotations = response.text_annotations
    return annotations[0].description if annotations else ""


############################################################
#              GEMINI MULTIMODAL CORRECTION
############################################################
def refine_text_with_gemini_and_image(prompt_text, image_path):
    if not GEMINI_API_KEY or not GEMINI_MODEL:
        return prompt_text

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    mime_type = "image/jpeg"

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        gemini_start_time = time.time()
        res = model.generate_content([
            {"mime_type": mime_type, "data": image_bytes},
            prompt_text,
        ])
        gemini_end_time = time.time()
        print("Time taken by Gemini:", gemini_end_time - gemini_start_time)
        return getattr(res, "text", prompt_text)

    except Exception:
        return prompt_text


############################################################
#                      MAIN LOGIC
############################################################
def main():
    speak("Welcome! Select an image file for text extraction.")

    img_path = choose_file()
    if not img_path:
        speak("No image selected.")
        return

    raw_text = extract_text_with_google_vision(img_path)
    print("Raw text extracted by Google Vision:", raw_text)

    refinement_prompt = f"""
                    Context: The text in "Extracted text" is the raw output from Google Vision API's detection on the image provided below. 

                    Extracted text:
                    {raw_text}

                    Task: Review the Vision API's detections in light of the actual visual evidence in the image. 
                    Your final output MUST be a single, natural-sounding, corrected, and comprehensive textual paragraph. 
                    Integrate all verified Vision detections and describe the content. 
                    If the image contains text (like from a book), include the complete, unsummarized text content. 
                    Enclose all direct text snippets or full text blocks within standard single quotation marks ('').
                    NEVER use the backslash character to enclose or separate text, quotes, or snippets. 
                    Summarize only contextual elements like book title, chapter, or page numbers separately from the quoted text. 
                    If the content is medical, issue a clear alarm. If no text is found by the Vision API, say "NO TEXT FOUND" and SUMMARIZE the visual WITHOUT mentioning the absence of text (25 WORDS ONLY).
                    Do NOT use headers, bullet points, or lists in your final response. NEVER mention Google Vision API.
                    """
    refined = refine_text_with_gemini_and_image(refinement_prompt, img_path)

    speak(refined)
    print("\nRefined OCR result:\n", refined)


if __name__ == "__main__":
    main()
