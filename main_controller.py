import sys
import os
import subprocess
import threading
import time

from gpiozero import Button, Device
from gpiozero.pins.lgpio import LGPIOFactory

from core.stt import listen
from core.tts_player import tts_main
from core.prompts import *
from core.priority_audio import AudioPriority, PriorityAudioManager

# ================================================================
# GPIO (CENTRALIZED – MAIN CONTROLLER ONLY)
# ================================================================
Device.pin_factory = LGPIOFactory()

EVENT_DIR = "/tmp/drishtikon_events"
os.makedirs(EVENT_DIR, exist_ok=True)

BUTTON_FILE = os.path.join(EVENT_DIR, "button")
BUTTON_COOLDOWN = 1.0
_last_button = 0

button = Button(17)

def emit(event):
    open(os.path.join(EVENT_DIR, event), "w").close()

def on_button():
    global _last_button
    now = time.monotonic()
    if now - _last_button < BUTTON_COOLDOWN:
        return
    _last_button = now
    emit("button")
    print("[GPIO] Button pressed")

button.when_pressed = on_button

# ================================================================
# PROCESS TRACKING
# ================================================================
active_processes = []
active_module = None

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
        time.sleep(0.5)

# ================================================================
# EVENT ROUTER (GPIO → ACTIVE MODULE)
# ================================================================
def event_router():
    global active_module
    while True:
        if os.path.exists(BUTTON_FILE):
            os.remove(BUTTON_FILE)
            if active_module:
                open(f"/tmp/{active_module}_button", "w").close()
                print(f"[ROUTER] button → {active_module}")
        time.sleep(0.05)

# ================================================================
# SUBPROCESS LAUNCHER
# ================================================================
def start_module(module_name: str, tag: str):
    global active_module

    active_module = tag
    p = subprocess.Popen([sys.executable, "-m", module_name])
    active_processes.append(p)

    while p.poll() is None:
        time.sleep(0.1)
    try:
        active_processes.remove(p)
    except Exception as e:
        print(f"Exception encountered when trying to remove {p}")
    active_module = None

# ================================================================
# AUDIO HELPERS
# ================================================================
def play(tts=tts_main, audio_file_name=goodbye_p):
    tts.play(audio_file_name)
    tts.wait()

# ================================================================
# MAIN LOOP (NEVER EXITS)
# ================================================================
def main():
    threading.Thread(target=linux_stop_listener, daemon=True).start()
    threading.Thread(target=event_router, daemon=True).start()

    play(tts_main, system_ready_p)
    
    attempt = 0
    while attempt < 2:
        cmd = listen()
        if not cmd:
            attempt += 1
            continue

        cmd = cmd.lower()
        attempt = 0

        # -----------------------------
        # READING
        # -----------------------------
        if "read" in cmd:
            play(tts_main, opening_reading_p)
            start_module("reading.read", "reading")

        # -----------------------------
        # RAG SEARCH
        # -----------------------------
        elif "search" in cmd or "find" in cmd:
            play(tts_main, opening_search_p)
            start_module("reading.rag", "rag")

        # -----------------------------
        # OBJECT DETECTION
        # -----------------------------
        elif "detect" in cmd or "object" in cmd:
            play(tts_main, opening_detection_p)
            start_module("detection.detect", "detection")

        # -----------------------------
        # NAVIGATION
        # -----------------------------
        elif "navigate" in cmd:
            play(tts_main, navigation_p)
            start_module("navigation.navigate", "navigation")

        # -----------------------------
        # EXIT (SOFT)
        # -----------------------------
        elif "exit" in cmd or "quit" in cmd or "excerpt" in cmd:
            play(tts_main, goodbye_p)
            break

        else:
            play(tts_main, did_not_understand_p)

if __name__ == "__main__":
    main()
