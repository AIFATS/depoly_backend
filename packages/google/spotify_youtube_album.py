import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import json
import os
from fastapi import APIRouter, HTTPException
from .apicall import get_youtube_api_key

spotify_youtube_album_router = APIRouter()

# Spotify API Credentials
CLIENT_ID = "7b31e43463f645a792cfa502547eb87a"
CLIENT_SECRET = "26fa4934017f448d86ca2a7c502e0e1c"

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET
    )
)

# Exclude these genres
EXCLUDED_GENRES = [
    "folk",
    "dj",
    "devotional",
    "remix",
    "bhakti",
    "independent",
    "cover",
]


def convert_to_ist(utc_time):
    """Converts UTC timestamp to Indian Standard Time (IST)."""
    if utc_time:
        try:
            utc_dt = datetime.strptime(utc_time, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            ist_dt = utc_dt + timedelta(hours=5, minutes=30)
            return ist_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception as e:
            return "Invalid Date"
    return "Unknown Date"

JSON_FILENAME = "movie_albums.json"

def save_albums_to_json(data):
    """Saves album data to a JSON file with timestamps."""
    current_datetime = datetime.now().strftime("%d:%m:%Y %H:%M:%S")
    next_update_datetime = (datetime.now() + timedelta(hours=24)).strftime("%d:%m:%Y %H:%M:%S")

    json_data = {
        "file_inserted_datetime": current_datetime,
        "next_update_datetime": next_update_datetime,
        "albums": data
    }

    # If file exists, update timestamps
    if os.path.exists(JSON_FILENAME):
        with open(JSON_FILENAME, "r", encoding="utf-8") as file:
            try:
                existing_data = json.load(file)
                existing_data["file_inserted_datetime"] = current_datetime
                existing_data["next_update_datetime"] = next_update_datetime
                existing_data["albums"] = data  # Update album data
            except json.JSONDecodeError:
                existing_data = json_data  # If file is corrupted, reset it

        json_data = existing_data

    # Save updated data
    with open(JSON_FILENAME, "w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, indent=4, ensure_ascii=False)

def fetch_youtube_videos(query, language):
    """Fetches YouTube video details for a song."""
    api_key = get_youtube_api_key()
    if not api_key:
        return None

    search_query = f"{query} {language} Movie Song"
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={search_query}&type=video&maxResults=1&key={api_key}"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "items" in data and data["items"]:
            item = data["items"][0]
            video_id = item.get("id", {}).get("videoId", "N/A")
            return {
                "title": item["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "channel_title": item["snippet"]["channelTitle"],
                "description": item["snippet"]["description"],
                "published_at": convert_to_ist(item["snippet"]["publishedAt"]),
                "thumbnail_url": item["snippet"]["thumbnails"]["high"]["url"],
            }
    return None


def get_movie_albums(language):
    """Fetches only movie albums, filtering out Folk, DJ, and other non-movie albums."""
    query = f"{language} Movie Album"
    results = sp.search(
        q=query, type="album", limit=10, market="IN"
    )  # Fetch top 10 albums

    movie_albums = []
    for album in results["albums"]["items"]:
        album_name = album["name"].lower()
        if not any(
            genre in album_name for genre in EXCLUDED_GENRES
        ):  # Exclude unwanted genres
            movie_albums.append(
                {
                    "album_name": album["name"],
                    "album_url": album["external_urls"]["spotify"],
                    "album_id": album["id"],
                }
            )

    return movie_albums


def get_album_songs(album_id):
    """Retrieves album songs from Spotify."""
    tracks = sp.album_tracks(album_id)
    return tracks["items"], [track["name"] for track in tracks["items"]]


def process_song(song, album_language):
    """Wrapper function for YouTube search (used in multithreading)."""
    song_title = song["name"]
    youtube_result = fetch_youtube_videos(song_title, album_language)
    return {"song_title": song_title, "youtube_result": youtube_result}

def get_movie_albums_api(album_language: str):
    """FastAPI route to get only movie albums in a specific language with YouTube links."""
    movie_albums = get_movie_albums(album_language)

    if not movie_albums:
        raise HTTPException(
            status_code=404, detail="No movie albums found for the given language."
        )

    all_albums_data = []

    for album in movie_albums:
        album_name = album["album_name"]
        album_url = album["album_url"]
        album_id = album["album_id"]

        # Fetch album songs
        tracks, track_names = get_album_songs(album_id)

        songs_data = []

        # Multithreading for faster YouTube searches
        with ThreadPoolExecutor(max_workers=1) as executor:
            future_to_song = {
                executor.submit(process_song, track, album_language): track
                for track in tracks
            }
            for future in as_completed(future_to_song):
                songs_data.append(future.result())

        album_data = {
            "album_name": album_name,
            "album_url": album_url,
            "album_language": album_language,
            "songs": songs_data,
        }
        
        all_albums_data.append(album_data)

    # Save data to JSON file with timestamps
    save_albums_to_json(all_albums_data)

    return all_albums_data

@spotify_youtube_album_router.get("/get_movie_albums")
def send_json_response(album_language: str):
    """Checks next update time and returns JSON data accordingly."""
    
    # If JSON file does not exist, fetch new data
    if not os.path.exists(JSON_FILENAME):
        get_movie_albums_api(album_language)

    # Try reading the JSON file after fetching new data
    try:
        with open(JSON_FILENAME, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Error reading JSON file.")

    next_update_datetime = data.get("next_update_datetime")

    # Get the current datetime
    current_datetime = datetime.now().strftime("%d:%m:%Y %H:%M:%S")

    # If next_update_datetime has expired, fetch new data
    if next_update_datetime and current_datetime >= next_update_datetime:
        get_movie_albums_api(album_language)

        # Reload updated JSON file
        try:
            with open(JSON_FILENAME, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Error reading updated JSON file.")

    # Remove timestamps before returning
    data.pop("file_inserted_datetime", None)
    data.pop("next_update_datetime", None)

    return data