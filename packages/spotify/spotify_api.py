from fastapi import APIRouter, HTTPException
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime, timezone, timedelta
import requests
import json

# Create API router
spotify_api_router = APIRouter()

# Path to Spotify credentials JSON
CONFIG_PATH = "credentials/spotify-service-account.json"

# Load Spotify credentials from JSON file
def load_config():
    try:
        with open(CONFIG_PATH, "r") as config_file:
            return json.load(config_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading config: {e}")

config = load_config()
CLIENT_ID = config.get("spotify_client_id")
CLIENT_SECRET = config.get("spotify_client_secret")

if not CLIENT_ID or not CLIENT_SECRET:
    raise HTTPException(status_code=500, detail="Spotify API credentials are missing.")

# Initialize Spotify client
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET
    )
)

# Convert UTC date string to IST formatted string
def convert_utc_to_ist(utc_time_str):
    try:
        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        try:
            utc_time = datetime.strptime(utc_time_str, "%Y-%m-%d")
        except ValueError:
            return None

    ist_offset = timedelta(hours=5, minutes=30)
    ist_time = utc_time.replace(tzinfo=timezone.utc) + ist_offset
    return ist_time.strftime("%d:%m:%Y %H:%M:%S")

# Main endpoint - Fetch songs based on query
@spotify_api_router.get("/spotify")
def spotify_music_api(query: str = "telugu"):
    try:
        results = sp.search(q=query, type="track", limit=25, market="IN")
        tracks = results["tracks"]["items"]

        if not tracks:
            raise HTTPException(status_code=404, detail="No tracks found for the given query.")

        track_info_list = []
        for track in tracks:
            track_info = {
                "title": track["name"],
                "artist": track["artists"][0]["name"],
                "band": ", ".join([artist["name"] for artist in track["artists"]]),
                "url": track["external_urls"]["spotify"],
                "track_id": track["id"],
                "duration": track["duration_ms"],
                "release_date": convert_utc_to_ist(track["album"]["release_date"]),
                "picture": None,
            }

            # Load image if available
            album_images = track.get("album", {}).get("images", [])
            if album_images:
                track_info["picture"] = album_images[0]["url"]

            track_info_list.append(track_info)

        return {
            "query": query,
            "results": track_info_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
