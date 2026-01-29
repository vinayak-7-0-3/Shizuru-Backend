from __future__ import annotations

from datetime import datetime
from bson import ObjectId
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from pydantic import ConfigDict

from ..metadata.models import *


class PyObjectId(ObjectId):
    """Pydantic-friendly wrapper around bson.ObjectId."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """
        Replace v1’s `__get_validators__`.
        Accept a raw ObjectId or any string that *can* be an ObjectId.
        """
        def validate(v: Any) -> ObjectId:
            if isinstance(v, ObjectId):
                return v
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)

        # validate after converting from str
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.no_info_after_validator_function(
                validate,
                core_schema.union_schema([
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.str_schema(),
                ]),
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetCoreSchemaHandler
    ) -> JsonSchemaValue:
        """
        Replace v1’s `__modify_schema__`.
        Mark the field as a string so OpenAPI / JSON-schema look right.
        """
        schema = handler(core_schema)
        schema.update(type="string", format="objectid")
        return schema


class MongoBaseModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,         
        arbitrary_types_allowed=True,  
    )


class DBArtist(MongoBaseModel, BaseArtist):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DBAlbum(MongoBaseModel, BaseAlbum):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DBTrack(MongoBaseModel, BaseTrack):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DBUser(MongoBaseModel):
    username: str
    email: Optional[str] = None
    password_hash: str
    is_admin: bool = False
    playlists: List[PyObjectId] = []  # references to Playlist
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None


class DBLikedSongs(MongoBaseModel):
    user_id: PyObjectId
    song_id: PyObjectId
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DBPlaylist(MongoBaseModel):
    name: str
    user_id: PyObjectId  # reference to User
    song_ids: List[PyObjectId] = []  # references to Song
    is_public: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Specially for file not found
class DBTrash(MongoBaseModel):
    original_song_data: dict  # Store original song document incase of restoring or edits
    chat_id: int
    msg_id: int
    reason: str
    moved_at: datetime = Field(default_factory=datetime.utcnow)
    verified_by_admin: Optional[PyObjectId] = None  # reference to User (admin)
    status: str = "pending"  # pending, restored etc.....