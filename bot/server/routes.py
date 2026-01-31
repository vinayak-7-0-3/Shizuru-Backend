from fastapi import APIRouter

from .routers import auth, songs, artists, albums, search, webdav

router = APIRouter()

router.include_router(auth.router, tags=["Auth"])
router.include_router(songs.router, tags=["Songs"])
router.include_router(artists.router, tags=["Artists"])
router.include_router(albums.router, tags=["Albums"])
router.include_router(search.router, tags=["Search"])
router.include_router(webdav.router, tags=["WebDAV"])