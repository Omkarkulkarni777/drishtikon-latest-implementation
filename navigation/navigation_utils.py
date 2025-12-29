# navigation/navigation_utils.py

import re

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
        return "The route is straightforward with no complex turns."

    return "Then ".join(gist) + "."
