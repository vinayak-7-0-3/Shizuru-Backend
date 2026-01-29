from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm

from ...database.connection import mongo
from ...database.models import DBUser
from ...utils.auth import hash_password, verify_password, create_access_token, get_current_user, Config
from ..models import UserLogin, UserRegister, UserResponse, GenericResponse, Token

router = APIRouter()

@router.post("/register", response_model=GenericResponse)
async def register(user: UserRegister):
    if await mongo.db["users"].find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed = hash_password(user.password)
    new_user = DBUser(username=user.username, email=user.email, password_hash=hashed)
    await mongo.db["users"].insert_one(new_user.dict(by_alias=True))
    return {"message": "Registered successfully"}


@router.post("/login", response_model=Token)
async def login(user: UserLogin, response: Response):
    db_user = await mongo.db["users"].find_one({"username": user.username})
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    if not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid username or password")

    token = create_access_token({"sub": db_user["username"]})
    
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        secure=True, 
        samesite="lax",  # CSRF protection
        max_age=Config.ACCESS_TOKEN_EXPIRE * 60  #seconds
    )
    
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", response_model=GenericResponse)
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user = Depends(get_current_user)):
    return {"username": current_user["username"], "email": current_user["email"]}
