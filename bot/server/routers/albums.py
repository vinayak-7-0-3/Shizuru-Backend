from typing import List
from fastapi import APIRouter, HTTPException

from ...database.connection import mongo
from ...database.models import DBAlbum
from ...utils.web import paginate

router = APIRouter()

@router.get("/albums", response_model=List[DBAlbum])
async def get_albums(limit: int = 10, page: int = 1):
    paging = paginate(limit, page)
    cursor = mongo.db["albums"].find().skip(paging["skip"]).limit(paging["limit"])
    results = [DBAlbum(**album) async for album in cursor]
    return results

@router.get("/albums/{id}", response_model=DBAlbum)
async def get_album(id: str):
    album = await mongo.db["albums"].find_one({"album_id": id})
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    return DBAlbum(**album)
