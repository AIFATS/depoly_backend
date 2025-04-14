from fastapi import APIRouter
import logging
from packages.call_routes.google_routes import google_call_router
from packages.call_routes.spotify_routes import spotify_call_router
from packages.call_routes.download_routes import download_call_router


router = APIRouter()


router.include_router(google_call_router, prefix="/google")
router.include_router(spotify_call_router, prefix="/spotify")
router.include_router(download_call_router, prefix="/download")
