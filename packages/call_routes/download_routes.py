from fastapi import APIRouter
from packages.download_video_songs.video_download import video_download_router  # Import router, NOT function

download_call_router = APIRouter()

# Include the Google API routes
download_call_router.include_router(video_download_router, prefix="/music")