from fastapi import APIRouter

from .routers import auth, songs, artists, albums

router = APIRouter()

router.include_router(auth.router, tags=["Auth"])
router.include_router(songs.router, tags=["Songs"])
router.include_router(artists.router, tags=["Artists"])
router.include_router(albums.router, tags=["Albums"])