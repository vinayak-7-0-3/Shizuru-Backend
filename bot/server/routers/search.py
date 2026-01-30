from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
import re

from ...database.connection import mongo
from ...database.models import DBTrack, DBAlbum, DBArtist
from ...utils.web import paginate

router = APIRouter()

class SearchResponse(BaseModel):
    tracks: List[DBTrack] = []
    albums: List[DBAlbum] = []
    artists: List[DBArtist] = []

def create_fuzzy_regex(query: str):
    """
    Creates a regex that matches all terms in the query in any order.
    Escape special characters to avoid regex errors.
    """
    if not query:
        return None
        
    # primitive cleanup
    query = re.sub(r'[^\w\s]', '', query).strip()
    if not query:
        return None
        
    terms = query.split()
    # Create lookaheads for each term
    # (?=.*term1)(?=.*term2)
    pattern = "".join([f"(?=.*{re.escape(term)})" for term in terms])
    return re.compile(pattern, re.IGNORECASE)

@router.get("/search", response_model=SearchResponse)
async def search_everything(
    q: str = Query(..., min_length=1),
    type: str = Query("all", regex="^(all|track|album|artist)$"),
    limit: int = 20,
    page: int = 1
):
    regex = create_fuzzy_regex(q)
    response = SearchResponse()
    
    if not regex:
        return response

    paging = paginate(limit, page)


    # We can run these concurrently, but for simplicity/safety with motor/asyncio loop 
    # and connection pool, sequential await is fine for this scale.
    
    if type in ["all", "track"]:
        cursor = mongo.db["songs"].find(
            {"$or": [
                {"title": regex},
                {"album": regex}, 
                {"artist": regex}
            ]}
        ).skip(paging["skip"]).limit(paging["limit"])
        response.tracks = [DBTrack(**doc) async for doc in cursor]

    if type in ["all", "album"]:
        cursor = mongo.db["albums"].find(
            {"$or": [
                {"title": regex},
                {"artist": regex}
            ]}
        ).skip(paging["skip"]).limit(paging["limit"])
        response.albums = [DBAlbum(**doc) async for doc in cursor]

    if type in ["all", "artist"]:
        cursor = mongo.db["artists"].find(
            {"name": regex}
        ).skip(paging["skip"]).limit(paging["limit"])
        response.artists = [DBArtist(**doc) async for doc in cursor]

    return response
