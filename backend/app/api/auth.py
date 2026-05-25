from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.schemas import UserLogin, Token
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings

router = APIRouter()

# Mock user database for local enterprise deployment
MOCK_USERS_DB = {
    "enterprise_dev": get_password_hash("securepass123")
}

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    user_hash = MOCK_USERS_DB.get(user_credentials.username)
    if not user_hash or not verify_password(user_credentials.password, user_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_credentials.username},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
