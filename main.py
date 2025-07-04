from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from auth import (
    User, UserCreate, Token,
    create_user, authenticate_user, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, regenerate_api_key, check_usage_limit, update_usage_limit, get_user_by_email
)
from api import extract, classify, multi_extract, detect_type
from datetime import timedelta, datetime
from pydantic import BaseModel, Field, validator
from typing import Union, Dict, List, Optional
import logging
from starlette.middleware.sessions import SessionMiddleware
from database import users, generate_api_key, log_api_usage, get_user_usage_stats
from fastapi.responses import JSONResponse
import secrets
import time
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting configuration
limiter = Limiter(key_func=get_remote_address)

# Environment variable to toggle API key requirement
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "true").lower() == "true"

app = FastAPI(
    title="Data Extractor API",
    description="""
    An API for extracting structured data from unstructured text using AI.
    
    ## Features
    - Extract specific fields from free-form text
    - Support for custom field aliases
    - Consistent JSON output with null for missing fields
    - Comprehensive error handling
    - User authentication with JWT tokens
    - Rate limiting protection against abuse
    
    ## Authentication & Security
    - Two modes: API key authentication or rate-limited public access
    - Rate limiting: 10 requests per minute per IP address
    - Set REQUIRE_API_KEY=false for public testing (Zyla submission)
    - Set REQUIRE_API_KEY=true for production with full user management
    
    ## Authentication (when REQUIRE_API_KEY=true)
    - Register a new user: POST /register
    - Login to get access token: POST /login
    - Use the access token in the Authorization header for protected endpoints
    
    ## Usage Tips
    - Provide clear, well-formatted text for best results
    - Use field aliases for custom output field names
    - Check response status codes for error handling
    - Respect rate limits to avoid 429 errors
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    separate_input_output_schemas=False
)

# Add rate limiter to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS and Session
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")  # Change in production

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(extract.router, prefix="/api")
app.include_router(classify.router, prefix="/api")
app.include_router(multi_extract.router, prefix="/api", tags=["Multi-Record Extraction"])
app.include_router(detect_type.router, prefix="/api", tags=["Type Detection"])

async def get_current_user_from_session(request: Request):
    """Get current user from session"""
    if "user" not in request.session:
        return None
    
    try:
        return request.session["user"]
    except:
        return None

# Web Routes
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request):
    """Render the home page"""
    current_user = await get_current_user_from_session(request)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": current_user
    })

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """Render the login page"""
    current_user = await get_current_user_from_session(request)
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "user": None
    })

@app.post("/login", include_in_schema=False)
async def login_web(request: Request):
    """Handle web login"""
    form = await request.form()
    email = form.get("email")
    password = form.get("password")

    if not email or not password:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Email and password are required",
                "user": None
            },
            status_code=400
        )

    user = authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Incorrect email or password",
                "user": None
            },
            status_code=400
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=access_token_expires
    )
    
    # Store user data in session
    request.session["access_token"] = access_token
    request.session["user"] = {
        "id": str(user["_id"]),
        "email": user["email"],
        "api_key": user.get("api_key")
    }
    
    response = RedirectResponse(url="/", status_code=302)
    return response

@app.get("/register", response_class=HTMLResponse, include_in_schema=False)
async def register_page(request: Request):
    """Render the registration page"""
    current_user = await get_current_user_from_session(request)
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "user": None
    })

@app.post("/register", include_in_schema=False)
async def register_web(request: Request):
    """Handle web registration"""
    form = await request.form()
    
    if form.get("password") != form.get("confirm_password"):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Passwords do not match",
                "user": None
            },
            status_code=400
        )
    
    try:
        user_data = UserCreate(email=form.get("email"), password=form.get("password"))
        user = create_user(user_data)
        return RedirectResponse(url="/login", status_code=302)
    except HTTPException as e:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": e.detail,
                "user": None
            },
            status_code=e.status_code
        )

@app.get("/logout", include_in_schema=False)
async def logout(request: Request):
    """Handle logout"""
    # Clear session
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)



@app.get("/apikeys", response_class=HTMLResponse, include_in_schema=False)
async def apikeys_page(request: Request, success: str = None, error: str = None):
    """Render the API keys page"""
    current_user = await get_current_user_from_session(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("apikeys.html", {
        "request": request,
        "user": current_user,
        "success": success,
        "error": error
    })

@app.post("/apikeys/regenerate", response_model=dict, include_in_schema=False)
async def regenerate_api_key(request: Request):
    """Regenerate API key for the current user"""
    current_user = await get_current_user_from_session(request)
    if not current_user:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"}
        )
    
    try:
        # Generate a new API key
        new_api_key = secrets.token_urlsafe(32)
        
        # Update the user's API key in the database using email as identifier
        result = users.update_one(
            {"email": current_user["email"]},
            {"$set": {"api_key": new_api_key}}
        )
        
        if result.modified_count == 0:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to update API key"}
            )
        
        # Update session with new API key
        request.session["user"]["api_key"] = new_api_key
        
        return {"api_key": new_api_key}
    except Exception as e:
        logger.error(f"Error regenerating API key: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/usage", response_class=HTMLResponse, include_in_schema=False)
async def usage_page(request: Request):
    """Render the usage page"""
    logger.info("Accessing usage page")
    
    current_user = await get_current_user_from_session(request)
    if not current_user:
        logger.warning("No user found in session")
        return RedirectResponse(url="/login", status_code=302)
    
    logger.info(f"Current user from session: {current_user}")
    
    # Get usage statistics for the current user

    user =  get_user_by_email(current_user.get("email"))
    logger.info(f"User: {user}")
    user_id = user.get("id")

    if user_id is None:
        # If no ID in session, try to get user from database
        logger.info(f"No user ID in session, looking up by email: {current_user.get('email')}")
        db_user = users.find_one({"email": current_user.get("email")})
        if db_user:
            user_id = db_user.get("id")
            logger.info(f"Found user ID from database: {user_id}")
        else:
            logger.warning("User not found in database")
            return RedirectResponse(url="/login", status_code=302)
    
    usage_stats = await get_user_usage_stats(user_id)
    if usage_stats is None:
        logger.error(f"Could not get usage stats for user {user_id}")
        return RedirectResponse(url="/login", status_code=302)
    
    logger.info(f"Usage stats for user {user_id}: {usage_stats}")
    
    # Format timestamps in usage history for display
    for call in usage_stats["usage_history"]:
        if "timestamp" in call:
            # Convert timestamp to string in a readable format
            call["timestamp"] = call["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    
    template_data = {
        "request": request,
        "user": current_user,
        "total_calls": usage_stats["total_calls"],
        "monthly_calls": usage_stats["monthly_calls"],
        "remaining_quota": usage_stats["remaining_quota"],
        "usage_history": usage_stats["usage_history"]
    }
    logger.info(f"Template data: {template_data}")
    
    return templates.TemplateResponse("usage.html", template_data)