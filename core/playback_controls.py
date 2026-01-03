import time
import os
import sys

from core.prompts import (
    goodbye_p,
    generating_answer_p,
    stopping_response_p,
    pause_beep,
)
from core.tts_player import tts_main

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
# NON-BLOCKING KEY READ (CROSS-PLATFORM)
# ================================================================
if os.name == "nt":
    import msvcrt

    def read_key_nonblocking():
        if msvcrt.kbhit():
            return msvcrt.getwch().lower()
        return None

else:
    import select
    import termios
    import tty

    def read_key_nonblocking():
        if not sys.stdin.isatty():
            return None

        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1).lower()
        return None

# ================================================================
# BLOCKING KEY WAIT
# ================================================================
def wait_for_key(valid_keys=None, sleep=0.05):
    if os.name == "nt":
        while True:
            key = read_key_nonblocking()
            if key and (valid_keys is None or key in valid_keys):
                return key
            time.sleep(sleep)

    if not sys.stdin.isatty():
        return None

    import termios, tty, select

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        while True:
            if select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.read(1).lower()
                if valid_keys is None or key in valid_keys:
                    return key
            time.sleep(sleep)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# ================================================================
# AUDIO HELPERS
# ================================================================
def play(tts=tts_main, audio_file_name=goodbye_p):
    tts.play(audio_file_name)
    tts.wait()


def non_blocking_play(
    tts=tts_main,
    audio_file_name=generating_answer_p,
    cmd_to_stop_audio_file="Press button to stop",
    stop_audio_file_name=stopping_response_p,
    in_a_loop=False,
    module_name="reading"
):
    """
    GPIO-free reactive playback.
    Stops on routed button OR keyboard 'v'.
    """
    tts.play(audio_file_name)
    print(cmd_to_stop_audio_file)
    
    global BUTTON_FILE
    BUTTON_FILE = f"/tmp/{module_name}_button"

    while tts.is_playing():
        btn = poll_button_event()
        key = read_key_nonblocking()

        if btn == "v" or key == "v":
            if in_a_loop:
                play(tts_main, pause_beep)
                return True
            play(tts, stop_audio_file_name)
            break

        time.sleep(0.05)

    return False
