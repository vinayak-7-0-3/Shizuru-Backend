from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, GetCoreSchemaHandler


class BaseTrack(BaseModel):
    chat_id: Optional[int] = None #keeping it optional, but is necessary
    msg_id: Optional[int] = None  #keeping it optional, but is necessary
    file_unique_id: Optional['str'] = None
    file_size: Optional[int] = None
    file_name: Optional[str] = None

    title: str
    track_id: Optional[str] = None

    artist: str
    artist_id: Optional[str] = None

    album: Optional[str] = None
    album_id: Optional[str] = None

    isrc: Optional[str] = None
    track_no: Optional[int] = None
    provider: str
    duration: Optional[int] = None
    tags: Optional[List[str]] = None
    mime_type: Optional[str] = None
    cover_url: Optional[str] = None


class BaseArtist(BaseModel):
    name: str
    artist_id: Optional[str] = None
    provider: str
    tags: Optional[List[str]] = None
    bio: Optional[str] = None
    cover_url: Optional[str] = None

# strictly checked
# should only be made using real metadata
class BaseAlbum(BaseModel):
    title: str
    album_id: str
    artist: str
    artist_id: str
    provider: str
    track_count: int
    upc: Optional[str] = None
    tags: Optional[List[str]] = None
    cover_url: Optional[str] = None