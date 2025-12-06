# core/prompts.py
# ================================================================
# CENTRALIZED PROMPT AUDIO (WAV CACHED)
# - All system prompts are generated once via speak_cached()
# - Ensures stable Pi playback (no MP3 decoding)
# ================================================================

from core.tts import speak_cached
from core.utils import absolute_path

# ---------------------------
# MAIN SYSTEM PROMPTS
# ---------------------------
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

all_done_p = speak_cached(
    "Completed all sentences.",
    "all_sentences_done.wav"
)

exiting_module_p = speak_cached(
    "Exiting reading module.",
    "exiting_module.wav"
)

return_to_reading_p = speak_cached(
    "Returning to reading.",
    "return_to_reading.wav"
)


# ---------------------------
# PAUSE MENU PROMPTS
# ---------------------------
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


# ---------------------------
# VOICE CONTROL PROMPTS
# ---------------------------
vc_intro_p = speak_cached(
    "Voice control. Say summary, resume, or quit.",
    "voice_intro.wav"
)

vc_retry_p = speak_cached(
    "I did not catch that. Please try again.",
    "retry_voice.wav"
)

vc_unknown_p = speak_cached(
    "Unknown command. Please say summary, resume, or quit.",
    "unknown_command.wav"
)

vc_back_p = speak_cached(
    "Back to voice control.",
    "back_voice.wav"
)


# ---------------------------
# BEEPS (non‑TTS files)
# ---------------------------
pause_beep = absolute_path("sounds", "pause_beep.wav")
resume_beep = absolute_path("sounds", "resume_beep.wav")
