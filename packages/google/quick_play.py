from fastapi import APIRouter, HTTPException, BackgroundTasks
import time
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from ytmusicapi import YTMusic
from concurrent.futures import ThreadPoolExecutor, as_completed

quick_play_Call_router = APIRouter()
ytmusic = YTMusic()

def format_youtube_release_date(iso_date_str):
    try:
        dt = datetime.fromisoformat(iso_date_str)
        return dt.strftime("%d-%m-%Y %H:%M:%S")
    except Exception:
        return "N/A"

def setup_driver():
    options = Options()
    options.binary_location = r"/usr/bin/brave-browser"  # Path to Brave browser
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")
    options.add_argument("--no-sandbox")  # Disable the sandbox for Docker environments
    options.add_argument("--disable-dev-shm-usage")  # Fix shared memory issues in Docker
    options.add_argument("--headless")  # Run in headless mode (no GUI)
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def fetch_song_metadata(video_id, href):
    try:
        song_info = ytmusic.get_song(video_id)
        song_title = song_info["videoDetails"]["title"]
        song_artist = song_info["videoDetails"]["author"]
        duration = song_info["videoDetails"]["lengthSeconds"]
        views = song_info["videoDetails"]["viewCount"]
        thumbnail = song_info["videoDetails"]["thumbnail"]["thumbnails"][-1]["url"]
        release_date = (
            song_info.get("microformat", {})
            .get("microformatDataRenderer", {})
            .get("publishDate", None)
        )
        release_date = format_youtube_release_date(release_date) if release_date else "N/A"

        return {
            "title": song_title,
            "video_url": href,
            "artist": song_artist,
            "duration": duration,
            "views": views,
            "thumbnail_url": thumbnail,
            "release_date": release_date
        }
    except Exception as e:
        print(f"Error processing video ID {video_id}: {e}")
        return None

def scrape_latest_songs_by_language(language: str):
    search_query = f"latest {language} songs"
    url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"

    driver = setup_driver()
    driver.get(url)

    time.sleep(2)
    for _ in range(3):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(1)

    video_links = driver.find_elements(By.CSS_SELECTOR, "a#video-title")
    seen = set()
    tasks = []
    videos = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        for video in video_links:
            href = video.get_attribute("href")

            if not href or "/watch" not in href:
                continue

            parsed = urlparse(href)
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if not video_id:
                continue

            tasks.append(executor.submit(fetch_song_metadata, video_id, href))

        for future in as_completed(tasks):
            result = future.result()
            if result:
                key = (result["title"], result["artist"])
                if key in seen:
                    continue
                seen.add(key)
                videos.append(result)

            if len(videos) >= 20:
                break

    driver.quit()

    return {
        "query": search_query,
        "results": videos
    }

def refresh_json_in_background(language: str, file_path: str):
    try:
        result_json = scrape_latest_songs_by_language(language)

        now = datetime.now()
        inserted_dt_str = now.strftime("%d-%m-%Y %H:%M:%S")
        next_update_dt_str = (now + timedelta(hours=24)).strftime("%d-%m-%Y %H:%M:%S")

        result_json["file_inserted_datetime"] = inserted_dt_str
        result_json["next_update_datetime"] = next_update_dt_str

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)

        print(f"[✔] Refreshed and saved latest {language} songs.")
    except Exception as e:
        print(f"[❌] Background update failed: {e}")

@quick_play_Call_router.get("/quickplay")
def quick_play_json_response(language: str, background_tasks: BackgroundTasks):
    try:
        json_dir = os.path.join("downloads", "json")
        os.makedirs(json_dir, exist_ok=True)

        file_name = f"latest_{language.lower().replace(' ', '_')}_songs.json"
        file_path = os.path.join(json_dir, file_name)

        # Check and serve existing cached file
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

            next_update_str = existing_data.get("next_update_datetime")
            if next_update_str:
                next_update_dt = datetime.strptime(next_update_str, "%d-%m-%Y %H:%M:%S")

                # If still valid, return it directly
                if datetime.now() < next_update_dt:
                    response_data = existing_data.copy()
                    response_data.pop("file_inserted_datetime", None)
                    response_data.pop("next_update_datetime", None)
                    return response_data                   

                # If expired, return cached data & trigger background update
                background_tasks.add_task(refresh_json_in_background, language, file_path)
                response_data = existing_data.copy()
                response_data.pop("file_inserted_datetime", None)
                response_data.pop("next_update_datetime", None)
                return  response_data               

        # If no file, create from scratch (blocking)
        result_json = scrape_latest_songs_by_language(language)
        now = datetime.now()
        inserted_dt_str = now.strftime("%d-%m-%Y %H:%M:%S")
        next_update_dt_str = (now + timedelta(hours=24)).strftime("%d-%m-%Y %H:%M:%S")

        result_json["file_inserted_datetime"] = inserted_dt_str
        result_json["next_update_datetime"] = next_update_dt_str

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result_json, f, indent=2, ensure_ascii=False)

        response_data = result_json.copy()
        response_data.pop("file_inserted_datetime", None)
        response_data.pop("next_update_datetime", None)

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))