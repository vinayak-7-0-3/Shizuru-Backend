from pydantic import BaseModel


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