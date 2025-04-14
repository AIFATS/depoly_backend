from fastapi import APIRouter
from packages.spotify.spotify_api import (
    spotify_api_router,
)  # Import router, NOT function

spotify_call_router = APIRouter()

# Include the Google API routes
spotify_call_router.include_router(spotify_api_router, prefix="/spotify")
