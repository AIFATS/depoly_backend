import re
import time
import json
import os
import threading
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks
from selenium import webdriver
from ytmusicapi import YTMusic
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

Flair_Call_router = APIRouter()

JSON_FILENAME = "YOUTUBE_WEB_SCRAPING.json"
ytmusic = YTMusic()


def setup_driver(headless=False):
    try:
        options = webdriver.ChromeOptions()
        options.binary_location = r"/usr/bin/brave-browser"
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--log-level=3")
        if headless:
            options.add_argument("--headless")
        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error setting up the browser driver: {str(e)}"
        )


def extract_playlists(driver):
    try:
        driver.get("https://www.youtube.com/music")
        driver.maximize_window()
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        last_height = driver.execute_script(
            "return document.documentElement.scrollHeight"
        )
        while True:
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)
            new_height = driver.execute_script(
                "return document.documentElement.scrollHeight"
            )
            if new_height == last_height:
                break
            last_height = new_height

        soup = BeautifulSoup(driver.page_source, "html.parser")
        all_playlists = {}
        sections = soup.find_all("h2")

        for section in sections:
            section_name = section.text.strip()
            section_playlists = []
            next_element = section.find_next()
            while next_element and next_element.name != "h2":
                for a_tag in next_element.find_all("a", href=True):
                    href = a_tag["href"]
                    if "/playlist" in href:
                        full_link = "https://www.youtube.com" + href
                        cleaned_link = re.sub(r"&playnext=1&index=\d+", "", full_link)
                        playlist_name_tag = a_tag.find_next("span")
                        if playlist_name_tag:
                            playlist_name = playlist_name_tag.text.strip()
                            if (
                                playlist_name
                                and not any(
                                    p["url"] == cleaned_link for p in section_playlists
                                )
                                and len(section_playlists) < 10
                            ):
                                img_tag = a_tag.find_next("img")
                                thumbnail_url = (
                                    img_tag["src"]
                                    if img_tag and img_tag.get("src")
                                    else "No Thumbnail"
                                )
                                section_playlists.append(
                                    {
                                        "name": playlist_name,
                                        "url": cleaned_link,
                                        "thumbnail_url": thumbnail_url,
                                    }
                                )
                next_element = next_element.find_next()
            if section_playlists:
                all_playlists[section_name] = section_playlists[:10]
        return all_playlists
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error extracting playlists: {str(e)}"
        )


def format_youtube_release_date(iso_date_str):
    try:
        dt = datetime.fromisoformat(iso_date_str)
        return dt.strftime("%d-%m-%Y %H:%M:%S")
    except Exception as e:
        print(f"Invalid date format: {iso_date_str} - {e}")
        return "Invalid Date"


def get_playlist_videos(driver, playlist_url, limit=5):
    try:
        driver.get(playlist_url)
        time.sleep(2)
        for _ in range(3):
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            time.sleep(1)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        videos = []
        for video in soup.select("a#video-title")[:limit]:
            title = video.get("title", "No Title")
            video_url = "https://www.youtube.com" + video["href"]
            parsed = urlparse(video_url)
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if not video_id:
                continue
            song_info = ytmusic.get_song(video_id)
            title = song_info["videoDetails"]["title"]
            artist = song_info["videoDetails"]["author"]
            duration = song_info["videoDetails"]["lengthSeconds"]
            views = song_info["videoDetails"]["viewCount"]
            thumbnail = song_info["videoDetails"]["thumbnail"]["thumbnails"][-1]["url"]
            release_date = (
                song_info.get("microformat", {})
                .get("microformatDataRenderer", {})
                .get("publishDate", "N/A")
            )
            release_date = (
                format_youtube_release_date(release_date)
                if release_date != "N/A"
                else "N/A"
            )
            videos.append(
                {
                    "title": title,
                    "video_url": video_url,
                    "artist": artist,
                    "duration": duration,
                    "views": views,
                    "thumbnail_url": thumbnail,
                    "release_date": release_date,
                }
            )
        return videos
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error extracting videos from playlist: {str(e)}"
        )


def process_playlist(bucket_name, playlists, results):
    try:
        driver = setup_driver(headless=True)
        results[bucket_name] = []
        for playlist in playlists:
            videos = get_playlist_videos(driver, playlist["url"])
            results[bucket_name].append(
                {"playlist_name": playlist["name"], "videos": videos}
            )
        driver.quit()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing playlist: {str(e)}"
        )


def save_albums_to_json(data):
    """Saves album data to a JSON file with timestamps."""
    current_datetime = datetime.now().strftime("%d:%m:%Y %H:%M:%S")
    next_update_datetime = (datetime.now() + timedelta(hours=24)).strftime(
        "%d:%m:%Y %H:%M:%S"
    )

    json_data = {
        "file_inserted_datetime": current_datetime,
        "next_update_datetime": next_update_datetime,
        "albums": data,
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


def webscraping():
    try:
        driver = setup_driver()
        playlists_data = extract_playlists(driver)
        driver.quit()

        # Save extracted playlists data to a file
        with open("youtube_music_playlists.json", "w", encoding="utf-8") as f:
            json.dump(playlists_data, f, indent=2, ensure_ascii=False)

        all_results = {}
        threads = []
        for bucket_name, playlists in playlists_data.items():
            thread = threading.Thread(
                target=process_playlist, args=(bucket_name, playlists, all_results)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Save final results (videos data) to a file
        save_albums_to_json(all_results)
        return all_results
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error during web scraping: {str(e)}"
        )


@Flair_Call_router.get("/ytwsj")
def send_json_response(background_tasks: BackgroundTasks):
    """Checks next update time and returns JSON data accordingly."""

    # If JSON file does not exist, fetch new data
    print("Checking if JSON file exists...")
    if not os.path.exists(JSON_FILENAME):
        print("JSON file does not exist. Fetching new data...")
        background_tasks.add_task(webscraping)
    print("JSON file exists. Proceeding to read it...")
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
    print(f"Current datetime: {current_datetime}")
    print(f"Next update datetime: {next_update_datetime}")
    if next_update_datetime and current_datetime >= next_update_datetime:
        background_tasks.add_task(webscraping)

        # Reload updated JSON file
        try:
            with open(JSON_FILENAME, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500, detail="Error reading updated JSON file."
            )

    # Remove timestamps before returning
    data.pop("file_inserted_datetime", None)
    data.pop("next_update_datetime", None)

    return data
