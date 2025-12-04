# utils.py (Raspberry Pi compatible)

import os
import sys

# ================================================================
#  BASE DIRECTORY (project root)
# ================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def absolute_path(*paths) -> str:
    """
    Returns an absolute path from the project root directory.
    Works reliably in Raspberry Pi, VSCode, Tkinter, etc.
    """
    return os.path.join(BASE_DIR, *paths)


# ================================================================
#  CREDENTIAL LOADING HELPER
# ================================================================
def load_credential_path(module_folder: str, filename: str) -> str:
    """
    Returns full path to: <module_folder>/cred/<filename>

    Example:
        load_credential_path("core", "stt-key.json")
        ==> BASE_DIR/core/cred/stt-key.json
    """
    return absolute_path(module_folder, "cred", filename)


# ================================================================
#  DIRECTORY ENSURER
# ================================================================
def ensure_dir(path: str):
    """
    Creates a folder safely on all OS (including RPi).
    """
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"[UTIL] Could not create directory {path}: {e}", file=sys.stderr)


# ================================================================
#  DEBUGGING OPTIONAL
# ================================================================
def debug_path(label: str, path: str):
    print(f"[DEBUG PATH] {label}: {path}")


if __name__ == "__main__":
    print("[UTIL] BASE_DIR =", BASE_DIR)
