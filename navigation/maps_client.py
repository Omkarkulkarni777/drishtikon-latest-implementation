# navigation/maps_client.py

import os
import googlemaps

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Allowed nearby place categories (speech-friendly)
ALLOWED_NEARBY_KEYWORDS = [
    "bus stop",
    "bus stand",
    "hospital",
    "clinic",
    "pharmacy",
    "medical store",
    "police station",
    "railway station",
    "metro station",
    "bank",
    "atm",
    "school",
    "university",
    "restaurant",
    "cafe",
    "supermarket",
    "grocery store",
    "mall",
    "post office",
    "library",
    "park",
    "gas station",
    "fuel station"
]

# FILTER USER QUERY
def is_valid_nearby_query(query: str) -> bool:
    query = query.lower()
    for kw in query.split():
        if kw in ALLOWED_NEARBY_KEYWORDS:
            return kw
    return False


def find_nearest_place(source, query):
    """
    Uses Places API to find nearest matching place.
    (Parameters unchanged as requested)
    """

    # Validate nearby place category
    if not is_valid_nearby_query(query):
        return "INVALID_CATEGORY"
        
    print(f"""\n {is_valid_nearby_query(query)} + " near " + {source} \n""")
    places = gmaps.places(
        query=is_valid_nearby_query(query) + " near " + source
    )

    if not places.get("results"):
        return None

    # Google already sorts by relevance
    for place in places["results"]:
        print(place)
        break
        print(place.get("distance", None))
    print("\n\n Above is the value of places['results'] \n\n")
    place = places["results"][0]
    location = place["geometry"]["location"]

    return {
        "name": place["name"],
        "coords": (location["lat"], location["lng"])
    }


def get_route(origin_coords, nearby_query):
    """
    1. Find nearest valid nearby place
    2. Fetch walking route to it
    """
    try:
        nearest = find_nearest_place(origin_coords, nearby_query)

        if nearest == "INVALID_CATEGORY":
            return "INVALID_CATEGORY"

        if not nearest:
            return None

        directions = gmaps.directions(
            origin=origin_coords,
            destination=nearest["coords"],
            mode="walking"
        )

        if not directions:
            return None

        leg = directions[0]["legs"][0]

        steps = []
        for step in leg["steps"]:
            steps.append({
                "instruction": step["html_instructions"],
                "distance": step["distance"]["text"]
            })

        return {
            "place_name": nearest["name"],
            "steps": steps,
            "duration": leg["duration"]["text"],
            "distance": leg["distance"]["text"]
        }

    except Exception as e:
        print(f"[Maps Error] {e}")
        return None
