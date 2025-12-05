import sys
import os
import subprocess
import threading
import time

# Ensure project root in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.stt import listen
from core.tts import speak, speak_blocking
from core.logger import log
from core.utils import absolute_path


# ================================================================
#   PROCESS TRACKING
# ================================================================
active_processes = []


# ================================================================
#   EMERGENCY STOP (RPi Safe)
# ================================================================

def kill_all_processes():
    """Force-kills all active subprocesses."""
    print("[STOP] Terminating subprocesses...")

    for p in active_processes[:]:
        try:
            p.terminate()
            time.sleep(0.3)
            p.kill()
        except:
            pass

    active_processes.clear()

    # Close OpenCV windows (if any)
    try:
        import cv2
        cv2.destroyAllWindows()
    except:
        pass

    print("[STOP] Subprocesses terminated.")


def linux_stop_listener():
    """
    On Raspberry Pi, there is no global keyboard hook.
    So we listen for a simple file-based STOP trigger.
    If the user creates /tmp/stop.txt → system stops.
    """
    print("[STOP] Linux STOP listener active (create /tmp/stop.txt to force stop).")

    while True:
        if os.path.exists("/tmp/stop.txt"):
            print("[STOP] Emergency stop signal detected via /tmp/stop.txt.")
            speak_blocking("Emergency stop activated.")
            kill_all_processes()
            os._exit(0)
        time.sleep(1)


# ================================================================
#   MODULE LAUNCHER
# ================================================================

def start_process(relative_path):
    """Launch reading/yolo modules as subprocesses."""
    target = absolute_path(relative_path)

    if not os.path.exists(target):
        speak_blocking(f"Module {relative_path} not found.")
        log("MAIN", relative_path, "Missing module")
        return

    try:
        p = subprocess.Popen([sys.executable, target])
        active_processes.append(p)

        # Wait until the process exits
        while p.poll() is None:
            time.sleep(0.1)

        active_processes.remove(p)

    except Exception as e:
        log("MAIN", relative_path, f"Launch error: {e}")
        speak_blocking("Unable to launch module.")


# ================================================================
#   MAIN LOOP
# ================================================================

def main():
    speak_blocking("System ready. Say read, detect, or exit.")
    print("[MAIN] Awaiting commands...")

    # Start RPi-safe STOP listener
    threading.Thread(target=linux_stop_listener, daemon=True).start()

    while True:
        cmd = listen()
        if not cmd:
            continue

        cmd = cmd.lower().strip()
        print(f"[MAIN] Heard: {cmd}")

        # Reading module
        if "read" in cmd:
            speak_blocking("Opening reading module.")
            log("MAIN", "-", "Launch reading")
            start_process("reading/read.py")
            continue

        # Object detection module
        if "detect" in cmd or "object" in cmd:
            speak_blocking("Opening object detection module.")
            log("MAIN", "-", "Launch YOLO")
            start_process("yolo/detect.py")
            continue

        # Exit
        if "exit" in cmd or "quit" in cmd:
            speak_blocking("Goodbye.")
            kill_all_processes()
            break

        speak_blocking("I did not understand.")
        log("MAIN", "-", f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
