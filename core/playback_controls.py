import time
import os
import sys
from gpiozero import Button, Device
from gpiozero.pins.lgpio import LGPIOFactory

from core.prompts import (
    goodbye_p,
    generating_answer_p,
    stopping_response_p,
    pause_beep,
)
from core.tts_player import tts_main

# ================================================================
# GPIO SETUP
# ================================================================
Device.pin_factory = LGPIOFactory()

button = Button(17)


BUTTON_COOLDOWN = 5  # seconds
_last_press_time = 0

# Single event (poll-based)
button_event = None


def _on_button_pressed():
    global button_event, _last_press_time
    now = time.monotonic()

    if now - _last_press_time < BUTTON_COOLDOWN:
        return  # ignore bounce / rapid re-press

    _last_press_time = now
    button_event = "v"
    print("[GPIO] Button accepted → v")


button.when_pressed = _on_button_pressed

# ================================================================
# BUTTON INPUT API
# ================================================================
def read_button():
    """
    NON-BLOCKING.
    Returns button key once, then clears it.
    """
    global button_event
    if button_event:
        key = button_event
        button_event = None
        return key
    return None


def wait_for_button(key="v"):
    """
    BLOCKING.
    Use ONLY in idle / modal states.
    """
    print("Waiting for button press...")
    button.wait_for_press()
    print("Button pressed!")
    return key

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
        # Only works if attached to a real terminal
        if not sys.stdin.isatty():
            return None

        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1).lower()
        return None


# ================================================================
# BLOCKING KEY WAIT (CROSS-PLATFORM, FIXED)
# ================================================================
def wait_for_key(valid_keys=None, sleep=0.05):
    """
    Blocking key wait.
    - Windows: msvcrt
    - Linux: termios + cbreak (set ONCE per wait)
    """

    # ---------- Windows ----------
    if os.name == "nt":
        while True:
            key = read_key_nonblocking()
            if key and (valid_keys is None or key in valid_keys):
                return key
            time.sleep(sleep)

    # ---------- Linux / POSIX ----------
    if not sys.stdin.isatty():
        return None  # cannot work in GUI / redirected stdin

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)  # IMPORTANT: set once

        while True:
            if select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.read(1).lower()
                if valid_keys is None or key in valid_keys:
                    return key
            time.sleep(sleep)

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

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
):
    """
    GPIO-only reactive playback.
    No keyboard. No blocking GPIO.
    """
    tts.play(audio_file_name)
    print(cmd_to_stop_audio_file)
    global button_event
    button_event = None

    while tts.is_playing():
        btn = read_button()
        if btn == "v":
            if in_a_loop:
                play(tts_main, pause_beep)
                return True
            play(tts, stop_audio_file_name)
            break

        time.sleep(0.05)

    return False
