# navigation/navigate.py

from core.tts import speak, speak_cached
from core.tts_player import tts_main
from core.playback_controls import play, non_blocking_play
from core.prompts import (
    path_not_found_p,
    navigation_stop_p
)

from navigation.destination_input import get_source_and_nearby_place
from navigation.maps_client import get_route, is_valid_nearby_query
from navigation.navigation_utils import (
    build_direction_gist,
    should_provide_gist
)


def main():

    source, nearby_request = get_source_and_nearby_place()
    if not source or not nearby_request:
        play(tts_main, navigation_stop_p)
        return

    route = get_route(origin_coords=source, nearby_query=is_valid_nearby_query(nearby_request))

    if route == "INVALID_CATEGORY":
        play(
            tts_main,
            speak_cached(
            "I could not understand the place you asked for. Please say bus stop, hospital, police station, or pharmacy.",
            "nav_invalid_category.wav"
            )
        )
        return

    if not route:
        play(tts_main, path_not_found_p)
        play(tts_main, navigation_stop_p)
        return

    # Speak ETA
    eta_audio = speak(
        f"The nearest {is_valid_nearby_query(nearby_request)} is {route['distance']} away. "
        f"It will take approximately {route['duration']} by walking."
    )
    wants_to_stop = non_blocking_play(tts_main, eta_audio, in_a_loop=True, module_name="navigation")
    if wants_to_stop:
        play(tts_main, navigation_stop_p)
        return

    # Decide if gist should be provided
    if not should_provide_gist(route["distance"]):
        play(
            tts_main,
            speak_cached(
                "The location is far away. For safety, please seek assistance from a nearby person.",
                "nav_far_away_loc.wav"
            )
        )
        return

    # Speak gist
    gist = build_direction_gist(route["steps"])
    if gist:
        gist_audio = speak(
            f"To reach {route['place_name']}, {gist}"
        )
        non_blocking_play(tts_main, gist_audio)


if __name__ == "__main__":
    main()
