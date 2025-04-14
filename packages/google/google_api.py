from fastapi import APIRouter, HTTPException
import requests
from datetime import datetime, timezone, timedelta
import base64
from .apicall import get_youtube_api_key

# Create API router
google_api_router = APIRouter()


def get_video_details(video_id, api_key):
    """Fetch additional video details such as duration."""
    url = f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id={video_id}&key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get("items"):
            duration_iso = data["items"][0]["contentDetails"]["duration"]
            duration_seconds = convert_iso8601_duration(duration_iso)
            return duration_seconds
    return None


def convert_iso8601_duration(duration):
    """Convert ISO 8601 duration (PT4M30S) to seconds."""
    import isodate

    try:
        return int(isodate.parse_duration(duration).total_seconds())
    except Exception:
        return None


def convert_utc_to_ist(utc_time_str):
    # Parse the UTC time string
    utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%SZ")

    # Define IST offset (UTC+5:30)
    ist_offset = timedelta(hours=5, minutes=30)

    # Convert to IST
    ist_time = utc_time.replace(tzinfo=timezone.utc) + ist_offset

    # Format as DD:MM:YYYY HH:MM:SS
    return ist_time.strftime("%d:%m:%Y %H:%M:%S")


@google_api_router.get("/youtube")
def fetch_youtube_music(query: str):
    """Fetch YouTube music videos along with album details and metadata."""
    api_key = get_youtube_api_key()
    if not api_key:
        raise HTTPException(
            status_code=500, detail="YouTube API Key not found in Firebase"
        )

    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&videoCategoryId=10&maxResults=20&key={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises HTTP error if status is 4xx or 5xx
        data = response.json()

        videos = []
        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            title = item.get("snippet", {}).get("title")
            channel_title = item.get("snippet", {}).get(
                "channelTitle"
            )  # Often represents the artist/band
            description = item.get("snippet", {}).get(
                "description", ""
            )  # May contain album details
            published_at = item.get("snippet", {}).get(
                "publishedAt", ""
            )  # Original date-time
            thumbnail_url = (
                item.get("snippet", {})
                .get("thumbnails", {})
                .get("high", {})
                .get("url", "")
            )

            if video_id and title:
                # Get duration of the video
                duration = get_video_details(video_id, api_key)

                # Convert image to binary
                image_binary = fetch_image_as_binary(thumbnail_url)

                videos.append(
                    {
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "album": channel_title,
                        "artist": channel_title,  # Assuming channel name is the artist
                        "band": channel_title,  # Bands are not always available in YouTube API
                        "composer": None,  # YouTube API does not provide composer info
                        "copyright": None,  # YouTube does not directly provide copyright info
                        "track": None,  # No track number info in YouTube API
                        "year": (
                            published_at[:4] if published_at else None
                        ),  # Extract year from timestamp
                        "picture": image_binary,  # Binary image data
                        "date_time_original": convert_utc_to_ist(
                            published_at
                        ),  # Convert to IST
                        "duration": duration,  # Duration in seconds
                    }
                )

        results = {"query": query, "results": videos}

        if not videos:
            print("No videos found.")
            return {"message": "No videos found", "query": query}

        return results
    except requests.exceptions.RequestException as e:
        print(f"YouTube API request failed: {e}")
        raise HTTPException(status_code=500, detail=f"YouTube API request failed: {e}")


def fetch_image_as_binary(image_url):
    """Download image and convert to binary."""
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode(
                "utf-8"
            )  # Encode image as base64
    except Exception as e:
        print(f"Error fetching image: {e}")
    return None
