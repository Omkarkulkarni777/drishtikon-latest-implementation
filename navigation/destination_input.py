# navigation/destination_input.py

from core.tts_player import tts_main
from core.playback_controls import play
from core.stt import listen_continuous
from core.tts import speak
from core.prompts import (
    navigation_src_p,
    navigation_src_err_p,
    navigation_dest_p,
    navigation_dest_err_p
)


def get_source_and_nearby_place():
    # Ask for source
    play(tts_main, navigation_src_p)
    source = listen_continuous()

    if not source:
        play(tts_main, navigation_src_err_p)
        return None, None

    # Ask nearby place
    play(tts_main, navigation_dest_p)
    nearby_request = listen_continuous()

    if not nearby_request:
        play(tts_main, navigation_dest_err_p)
        return source, None

    confirm_audio = speak(
        f"You are at {source}. Searching for nearby {nearby_request}."
    )
    play(tts_main, confirm_audio)

    return source, nearby_request
