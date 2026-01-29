from typing import List
from fastapi import APIRouter, HTTPException

from ...database.connection import mongo
from ...database.models import DBArtist
from ...utils.web import paginate

router = APIRouter()

@router.get("/artists", response_model=List[DBArtist])
async def get_artists(limit: int = 10, page: int = 1):
    paging = paginate(limit, page)
    cursor = mongo.db["artists"].find().skip(paging["skip"]).limit(paging["limit"])
    results = [DBArtist(**artist) async for artist in cursor]
    return results

@router.get("/artists/{id}", response_model=DBArtist)
async def get_artist(id: str):
    artist = await mongo.db["artists"].find_one({"artist_id": id})
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return DBArtist(**artist)
