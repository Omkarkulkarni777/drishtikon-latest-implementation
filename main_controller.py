import sys
import os
import subprocess
import threading
import time

from core.stt import listen
from core.tts_player import tts_main
from core.prompts import *
from core.priority_audio import AudioPriority, PriorityAudioManager

# ================================================================
# PROCESS TRACKING
# ================================================================
active_processes = []

priority_audio = PriorityAudioManager(tts_main)

# ================================================================
# EMERGENCY STOP
# ================================================================

def kill_all_processes():
    for p in active_processes[:]:
        try:
            p.terminate()
            p.kill()
        except:
            pass
    active_processes.clear()

def linux_stop_listener():
    while True:
        if os.path.exists("/tmp/stop.txt"):
            os.remove("/tmp/stop.txt")
            play(tts_main, emergency_stop_p)
            kill_all_processes()
            os._exit(0)
        time.sleep(1)

# ================================================================
# SUBPROCESS LAUNCHER
# ================================================================

def start_module(module_name: str):
    p = subprocess.Popen(
        [sys.executable, "-m", module_name]
    )
    active_processes.append(p)

    while p.poll() is None:
        time.sleep(0.1)

    active_processes.remove(p)

# ================================================================
# AUDIO HELPERS
# ================================================================
def play(tts=tts_main, audio_file_name=goodbye_p):
    tts.play(audio_file_name)
    tts.wait()

# ================================================================
# MAIN LOOP
# ================================================================

def main():
    threading.Thread(target=linux_stop_listener, daemon=True).start()
    play(tts_main, system_ready_p)

    attempt = 0
    while attempt < 2:
        cmd = listen()
        if not cmd:
            attempt += 1
            continue

        cmd = cmd.lower()

        # -----------------------------
        # READING
        # -----------------------------
        if "read" in cmd:
            attempt = 0
            play(tts_main, opening_reading_p)
            start_module("reading.read")

        # -----------------------------
        # RAG SEARCH
        # -----------------------------
        elif "search" in cmd or "find" in cmd:
            attempt = 0
            play(tts_main, opening_search_p)
            start_module("reading.rag")
        # -----------------------------
        # OBJECT DETECTION
        # -----------------------------
        elif "detect" in cmd or "object" in cmd:
            attempt = 0
            play(tts_main, opening_detection_p)
            start_module("detection.detect")

        # -----------------------------
        # NAVIGATION (NEW)
        # -----------------------------
        elif "navigate" in cmd or "navigation" in cmd:
            attempt = 0
            play(tts_main, navigation_p)
            start_module("navigation.navigate")
        # -----------------------------
        # EXIT
        # -----------------------------
        elif "exit" in cmd or "quit" in cmd:
            play(tts_main, goodbye_p)
            kill_all_processes()
            break

        else:
            print(cmd)
            play(tts_main, did_not_understand_p)
    if attempt >= 2:
        play(tts_main, goodbye_p)
if __name__ == "__main__":
    main()
