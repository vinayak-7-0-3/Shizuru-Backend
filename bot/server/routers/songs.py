from typing import List
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse

from ...database.connection import mongo
from ...database.models import DBTrack
from ...utils.web import paginate, parse_range_header
from ...tgclient import botmanager

router = APIRouter()

@router.get("/songs", response_model=List[DBTrack])
async def get_songs(limit: int = 10, page: int = 1):
    paging = paginate(limit, page)
    cursor = mongo.db["songs"].find().skip(paging["skip"]).limit(paging["limit"])
    results = [DBTrack(**song) async for song in cursor]
    return results

@router.get("/songs/{id}", response_model=DBTrack)
async def get_song(id: str):
    song = await mongo.db["songs"].find_one({"track_id": id})
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return DBTrack(**song)


@router.get("/stream/{file_unique_id}")
async def stream_song(file_unique_id: str, request: Request):
    track = await mongo.db["songs"].find_one({"file_unique_id": file_unique_id})
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    db_track = DBTrack(**track)
    if not db_track.chat_id or not db_track.msg_id:
        raise HTTPException(status_code=400, detail="Missing chat_id/msg_id")

    bot = botmanager.get_available_bot()

    if not bot or not bot.bytestreamer:
        raise HTTPException(status_code=503, detail="Streaming bot unavailable")

    file_id = await bot.bytestreamer.get_file_properties(db_track.chat_id, db_track.msg_id)
    file_size = file_id.file_size or db_track.file_size or 10 * 1024 * 1024

    range_header = request.headers.get("range")
    start_byte, end_byte = parse_range_header(range_header, file_size)

    chunk_size = 512 * 1024
    offset = start_byte - (start_byte % chunk_size)
    first_part_cut = start_byte - offset
    last_part_cut = (end_byte % chunk_size) + 1
    total_bytes = end_byte - start_byte + 1

    part_count = ((end_byte - offset) // chunk_size) + 1

    stream_gen = bot.bytestreamer.yield_file(
        file_id=file_id,
        index=0,
        offset=offset,
        first_part_cut=first_part_cut,
        last_part_cut=last_part_cut,
        part_count=part_count,
        chunk_size=chunk_size
    )

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(total_bytes)
    }

    if range_header:
        headers["Content-Range"] = f"bytes {start_byte}-{end_byte}/{file_size}"
        status_code = 206
    else:
        status_code = 200

    return StreamingResponse(
        stream_gen,
        status_code=status_code,
        media_type=db_track.mime_type or "audio/mpeg",
        headers=headers
    )
