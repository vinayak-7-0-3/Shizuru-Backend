from typing import List
from pydantic import BaseModel
from ..database.models import DBAlbum, DBArtist, DBTrack


class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserResponse(BaseModel):
    username: str
    email: str
    
    
class Token(BaseModel):
    access_token: str
    token_type: str


class GenericResponse(BaseModel):
    message: str


class AlbumWithTracks(DBAlbum):
    tracks: List[DBTrack] = []


class ArtistDetailed(DBArtist):
    albums: List[DBAlbum] = []
    tracks: List[DBTrack] = []