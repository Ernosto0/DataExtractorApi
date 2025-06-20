from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database import users, generate_api_key, get_next_user_id
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")  # Change in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Models
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    api_key: Optional[str] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Password and Token functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = users.find_one({"email": token_data.email})
    if user is None:
        raise credentials_exception
    
    return User(**user)

# Database operations
def get_user_by_email(email: str):
    return users.find_one({"email": email})

def create_user(user: UserCreate):
    # Check if user already exists
    if get_user_by_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user with sequential ID and API key
    user_id = get_next_user_id()
    user_data = {
        "id": user_id,
        "email": user.email,
        "hashed_password": get_password_hash(user.password),
        "api_key": "Please regenerate api key",
        "is_api_key_active": True,
        "usage_limit": 100
    }
    
    result = users.insert_one(user_data)
    return User(**user_data)

def authenticate_user(email: str, password: str):
    user = get_user_by_email(email)
    logger.info(f"User: {user}")    
    if not user:
        logger.error(f"User not found: {email}")
        return False
    if not verify_password(password, user["hashed_password"]):
        logger.error(f"Invalid password for user: {email}")
        return False
    return user

def regenerate_api_key(user_id: int) -> str:
    """Regenerate API key for a user"""
    new_api_key = generate_api_key()
    users.update_one(
        {"id": user_id},
        {"$set": {"api_key": new_api_key}},
    )
    return new_api_key 

def usage_limit_reached(user_id: int):
    """Check if usage limit has been reached for a user"""
    user = users.find_one({"id": user_id})
    if user is None:
        return False
    return user["usage_limit_reached"]

def update_usage_limit(user_id: int, amount: int):
    """Update usage limit for a user -1"""\
    
    users.update_one(
        {"id": user_id},
        {"$inc": {"usage_limit": -amount}}
    )

    logger.info(f"Usage limit updated for user {user_id}: {amount}")

def check_usage_limit(user_id: int):
    """Check if user has usage limit"""
    user = users.find_one({"id": user_id})
    if user is None:
        return False
    
    logger.info(f"Usage limit for user {user_id}: {user['usage_limit']}")
    return user["usage_limit"]


