# navigation/navigation_manager.py

import threading
from core.tts_player import tts_main
from core.playback_controls import non_blocking_play, play
from core.tts import speak
from core.prompts import navigation_stop_p


class NavigationManager(threading.Thread):
    """
    Runs navigation instructions while object detection
    runs in parallel as a subprocess.

    Audio priority rules:
    - DETECTION > NAVIGATION
    - SYSTEM can interrupt everything
    """

    def __init__(self, steps):
        super().__init__(daemon=True)

        self.steps = steps                    # list of navigation steps
        self.running = True
        self.yolo_process = None

    # --------------------------------------------------
    # MAIN NAVIGATION LOOP
    # --------------------------------------------------
    def run(self):
        """
        Main thread execution.
        """

        # Iterate through navigation steps
        for step in self.steps:
            if not self.running:
                break

            instruction = step.get("instruction")
            if not instruction:
                continue

            instruction_audio = speak(instruction)
            wants_to_break_loop = non_blocking_play(tts_main, instruction_audio, in_a_loop=True)
            if wants_to_break_loop:
                self.stop()
                return

        # Navigation finished
        self.stop()

    # --------------------------------------------------
    # STOP EVERYTHING CLEANLY
    # --------------------------------------------------
    def stop(self):
        """
        Stops navigation and object detection.
        """
        self.running = False

        play(tts_main, navigation_stop_p)
