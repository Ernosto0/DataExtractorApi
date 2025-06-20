from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from utils import DataExtractor, OpenAIExtractor
from auth import (
    User, UserCreate, Token,
    create_user, authenticate_user, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from datetime import timedelta
from pydantic import BaseModel, Field, validator
from typing import Union, Dict, List, Optional
import logging
from starlette.middleware.sessions import SessionMiddleware
from database import users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExtractionRequest(BaseModel):
    text: str = Field(
        ..., 
        description="The text to extract information from",
        example="John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567"
    )
    fields: Union[List[str], Dict[str, str]] = Field(
        ..., 
        description="Fields to extract. Can be either a list of field names or a map of alias:field_name",
        examples=[
            ["name", "address", "phone"],
            {
                "customer_name": "name",
                "customer_address": "address",
                "contact_number": "phone"
            }
        ]
    )

    @validator('text')
    def text_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()

    @validator('fields')
    def fields_must_not_be_empty(cls, v):
        if isinstance(v, list) and (not v or not all(v)):
            raise ValueError('Fields list cannot be empty and must contain non-empty strings')
        if isinstance(v, dict) and (not v or not all(v.keys()) or not all(v.values())):
            raise ValueError('Fields map cannot be empty and must contain non-empty strings')
        return v

    class Config:
        schema_extra = {
            "example": {
                "text": "John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567",
                "fields": ["name", "address", "phone"]
            }
        }

class ExtractedData(BaseModel):
    """Model for successful extraction results"""
    message: str = Field(..., example="Data extracted successfully")
    data: Dict[str, Optional[Union[str, int, float]]] = Field(
        ...,
        description="Extracted data with field names as keys and extracted values or null. Values can be strings, integers, or floats.",
        example={
            "name": "John Doe",
            "address": "123 Main St, New York",
            "phone": "(555) 123-4567",
            "quantity": 3,
            "amount": 270.00
        }
    )

class ErrorResponse(BaseModel):
    """Model for error responses"""
    detail: Union[str, Dict[str, Optional[str]]] = Field(
        ...,
        description="Error details, either a string message or a structured error object",
        examples=[
            "Text cannot be empty",
            {
                "message": "Extraction failed",
                "error": "Failed to parse extraction result",
                "details": "Invalid JSON response"
            }
        ]
    )

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
    
    ## Authentication
    - Register a new user: POST /register
    - Login to get access token: POST /login
    - Use the access token in the Authorization header for protected endpoints
    
    ## Usage Tips
    - Provide clear, well-formatted text for best results
    - Use field aliases for custom output field names
    - Check response status codes for error handling
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

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

async def get_current_user_from_session(request: Request):
    """Get current user from session"""
    if "access_token" not in request.session:
        return None
    
    try:
        token = request.session["access_token"]
        current_user = await get_current_user(token)
        return current_user
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
    
    # Store token in session
    request.session["access_token"] = access_token
    
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
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@app.post(
    "/extract",
    response_model=ExtractedData,
    responses={
        200: {"description": "Successful extraction", "model": ExtractedData},
        400: {"description": "Invalid input", "model": ErrorResponse},
        422: {"description": "Extraction failed", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    tags=["extraction"]
)
async def extract_data(req: ExtractionRequest):
    """
    Extract structured data from unstructured text.

    This endpoint accepts text input and a specification of fields to extract,
    then uses AI to extract the requested information into a structured format.

    - **text**: The input text to extract information from
    - **fields**: Either a list of field names or a dictionary mapping aliases to field names
    """
    try:
        openai_extractor = OpenAIExtractor({"text": req.text}, fields=req.fields)
        result = openai_extractor.openai_api_call()
        
        if "error" in result:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Extraction failed",
                    "error": result["error"],
                    "details": result.get("details", None)
                }
            )
        
        logger.info(f"Data extracted successfully: {result}")
        return {
            "message": "Data extracted successfully",
            "data": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during extraction: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during extraction"
        )
   
    


