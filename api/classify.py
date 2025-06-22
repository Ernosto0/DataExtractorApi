from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
from fastapi import HTTPException
import time
from database import users,  log_api_usage
from auth import check_usage_limit, update_usage_limit
from services.classifier import OpenAIClassifier
from utils import ErrorResponse
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)

router = APIRouter( )


MAX_TEXT_LENGTH = 1000


class ClassificationRequest(BaseModel):
    """Model for classification requests"""
    apikey: str = Field(..., description="API key for authentication")
    text: str = Field(..., description="The text to classify")
    labels: List[str] = Field(..., description="The labels to classify the text into")

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

    @validator('labels')
    def labels_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('Labels cannot be empty')
        return v
    
    @validator('text')
    def text_must_be_less_than_characters(cls, v):
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f'Text cannot be more than {MAX_TEXT_LENGTH} characters')
        return v

    class Config:
        schema_extra = {
            "example": {
                "text": "I am having trouble logging in",
                "labels": ["Bug", "Feature Request", "Billing", "Login Issue"]
            }
        }
class ClassifiedData(BaseModel):
    """Model for successful classification results"""
    message: str = Field(..., example="Data classified successfully")
    data: Dict[str, List[str]] = Field(
        ...,
        description="Classification results with 'labels' key containing the matched labels",
        example={
            "labels": ["Bug", "Feature Request", "Billing", "Login Issue"]
        }
    )



@router.post("/classify", response_model=ClassifiedData, 
          responses={
              200: {"description": "Successful classification", "model": ClassifiedData},
              400: {"description": "Invalid input", "model": ErrorResponse},
              422: {"description": "Classification failed", "model": ErrorResponse},
              500: {"description": "Internal server error", "model": ErrorResponse}
          },
          tags=["classification"])
async def classify_data(req: ClassificationRequest):
    """Classify data using OpenAI"""
    start_time = time.time()  # Start timing the request
    
    try:
        logger.info(f"Classification request received: {req}")

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

        openai_classifier = OpenAIClassifier({"text": req.text}, fields=req.labels)
        result = openai_classifier.openai_api_call()
        
        # Calculate response time
        response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
        
        if isinstance(result, dict) and "error" in result:
            # Log failed attempt
            await log_api_usage(
                user_id=user.get("id"),
                endpoint="/classify",
                status="error",
                response_time=response_time
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Classification failed",
                    "error": result["error"],
                    "details": result.get("details", None)
                }
            )
        
        # Log successful attempt
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/classify",
            status="success",
            response_time=response_time
        )
        
        logger.info(f"Data classified successfully: {result}")
        return {
            "message": "Data classified successfully",
            "data": result
        }
        
    except ValueError as e:
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/classify",
            status="error",
            response_time=int((time.time() - start_time) * 1000)
        )
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/classify",
            status="error",
            response_time=int((time.time() - start_time) * 1000)
        )
        logger.error(f"HTTP error: {str(e.detail)}")
        raise e
    except Exception as e:
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/classify",
            status="error",
            response_time=int((time.time() - start_time) * 1000)
        )
        logger.error(f"Unexpected error during classification: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during classification: {str(e)}"
        )