from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
from fastapi import HTTPException
import time
from database import users, log_api_usage
from auth import check_usage_limit, update_usage_limit
from services.detect_typer import DetectTyper
from utils import ErrorResponse
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 1000

router = APIRouter()

class DetectTypeRequest(BaseModel):
    apikey: str = Field(
        ...,
        description="API key for authentication",
        example="1234567890"
    )

    text: str = Field(
        ..., 
        description="The text to detect the type of",
        example="Product: MacBook Pro\nPrice: $1299\nDate: June 2025\nSerial: ABC-1234"
    )

    fields: List[str] = Field(
        ...,
        description="The fields to detect the type of",
        example=["name", "price", "date", "serial"]
    )

    @validator('text')
    def text_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()

    @validator('apikey')
    def apikey_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('API key is required')
        return v.strip()

    @validator('text')
    def text_must_be_less_than_characters(cls, v):
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f'Text cannot be more than {MAX_TEXT_LENGTH} characters')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "apikey": "your-api-key-here",
                "text": "MacBook Pro\nPrice: $1299\nDate: June 2025\nSerial: ABC-1234",
                "fields": ["name", "price", "date", "serial"]
            }
        }

class DetectTypeResponse(BaseModel):
    message: str = Field(..., example="Type detection successful")
    data: Dict[str, str] = Field(..., example={"name": "product_name", "price": "currency", "date": "US_date", "serial": "alphanumeric_code"})

@router.post("/detect-type", response_model=DetectTypeResponse, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}})
async def detect_type(req: DetectTypeRequest):
    start_time = time.time()  # Start timing the request
    try:
        # Check if API key exists and get user
        if req.apikey is None:
            raise HTTPException(status_code=401, detail="API key is required")

        user = users.find_one({"api_key": req.apikey})
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Get user ID, falling back to email if ID is not present
        user_identifier = user.get("id") or user.get("_id") or user.get("email")
        if not user_identifier:
            raise HTTPException(status_code=500, detail="Invalid user data")

        if not check_usage_limit(user_identifier):
            raise HTTPException(status_code=402, detail="Usage limit reached. Please upgrade your plan.")

        update_usage_limit(user_identifier, 1)

        # Create detector instance and process
        detector = DetectTyper(text=req.text, fields=req.fields)
        result = detector.detect_type()
        response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds

        if "error" in result:
            # Log failed attempt
            await log_api_usage(
                user_id=user.get("id"),
                endpoint="/detect-type",
                status="error",
                response_time=response_time
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Detection failed",
                    "error": result["error"],
                    "details": result.get("details", None)
                }
            )
        
        # Log successful attempt
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/detect-type",
            status="success",
            response_time=response_time
        )
        # Update usage counter

        return DetectTypeResponse(
            message="Type detection successful",
            data=result
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in detect_type endpoint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

