from fastapi import APIRouter
from packages.google.google_api import google_api_router  # Import router, NOT function
from packages.google.spotify_youtube_album import spotify_youtube_album_router
from packages.google.Flair_Call import Flair_Call_router
from packages.google.quick_play import quick_play_Call_router  # Import router, NOT function

google_call_router = APIRouter()

# Include the Google API routes
google_call_router.include_router(google_api_router, prefix="/google")
google_call_router.include_router(spotify_youtube_album_router, prefix="/spotify")
google_call_router.include_router(Flair_Call_router, prefix="/webscraping")
google_call_router.include_router(quick_play_Call_router, prefix="/webscraping")