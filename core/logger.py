import datetime
import sys
import os

from core.utils import absolute_path, ensure_dir

# ================================================================
#  LOG FILE LOCATION
# ================================================================
LOG_DIR = absolute_path("results")
LOG_FILE = absolute_path("results", "app.log")

# Ensure logging directory exists
ensure_dir(LOG_DIR)


# ================================================================
#  LOGGER
# ================================================================
def log(service: str = "", image_path: str = "", message: str = "", time_taken=None):
    """
    Standardized logging function for reading, YOLO, STT, TTS, and main controller.
    Logs in the format:

    [2025-12-01 14:20:55]  SERVICE  image/path  message  (Time: x.xs)
    """

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Clean message (avoid huge multi-line text in logs)
    msg_preview = message.replace("\n", " ")[:300]

    try:
        entry = (
            f"[{timestamp}]\t{service}\t{image_path}\t{msg_preview}\t(Time: {time_taken}s)\n"
            if time_taken is not None
            else f"[{timestamp}]\t{service}\t{image_path}\t{msg_preview}\n"
        )

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

    except Exception as e:
        print(f"[LOGGER ERROR] {e}", file=sys.stderr)

if __name__ == "__main__":
    print("The [LOG FILE] is located at:", LOG_FILE)
    print("The [LOG DIRECTORY] is located at:", LOG_DIR)