from fastapi import APIRouter, HTTPException
import yt_dlp
import os
import base64

video_download_router = APIRouter()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@video_download_router.get("/youtube")
def video_download_music(videourl: str):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(videourl, download=True)
            filename = ydl.prepare_filename(info_dict)

        # Read the video and encode in base64
        with open(filename, "rb") as video_file:
            video_bytes = video_file.read()
            base64_str = base64.b64encode(video_bytes).decode('utf-8')

        # Delete the video file after encoding
        os.remove(filename)
        print(f"Deleted file: {filename}")
        print(f"Base64 string length: {len(base64_str)}")

        return {
            "message": "✅ Video downloaded and encoded",
            "filename": os.path.basename(filename),
            "base64": base64_str
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error: {str(e)}")
