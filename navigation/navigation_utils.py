# navigation/navigation_utils.py

import re

MAX_GIST_DISTANCE_KM = 1.5


def clean_text(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_direction_gist(steps, max_steps=3):
    """
    Builds a short, human-friendly navigation gist.
    """
    gist = []

    for step in steps[:max_steps]:
        instruction = clean_text(step["instruction"])
        gist.append(instruction)

    if not gist:
        return None

    return "Then ".join(gist) + "."


def should_provide_gist(distance_text):
    """
    Returns True if distance <= 1.5 km
    """
    try:
        km = float(distance_text.replace("km", "").strip())
        return km <= MAX_GIST_DISTANCE_KM
    except:
        return False
