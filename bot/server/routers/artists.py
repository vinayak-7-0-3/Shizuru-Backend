from typing import List
from fastapi import APIRouter, HTTPException

from ...database.connection import mongo
from ...database.models import DBArtist, DBAlbum, DBTrack
from ..models import ArtistDetailed
from ...utils.web import paginate

router = APIRouter()

@router.get("/artists", response_model=List[DBArtist])
async def get_artists(limit: int = 10, page: int = 1):
    paging = paginate(limit, page)
    cursor = mongo.db["artists"].find().skip(paging["skip"]).limit(paging["limit"])
    results = [DBArtist(**artist) async for artist in cursor]
    return results


@router.get("/artists/{id}", response_model=ArtistDetailed)
async def get_artist(id: str):
    artist = await mongo.db["artists"].find_one({"artist_id": id})
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Fetch all albums
    albums_cursor = mongo.db["albums"].find({"artist_id": id})
    albums = [DBAlbum(**album) async for album in albums_cursor]
    
    # Fetch 10 random tracks
    pipeline = [
        {"$match": {"artist_id": id}},
        {"$sample": {"size": 10}}
    ]
    tracks_cursor = mongo.db["songs"].aggregate(pipeline)
    tracks = [DBTrack(**track) async for track in tracks_cursor]

    return ArtistDetailed(**artist, albums=albums, tracks=tracks)
