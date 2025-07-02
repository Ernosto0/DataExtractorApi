from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
from fastapi import HTTPException
import time
from database import users,  log_api_usage
from auth import check_usage_limit, update_usage_limit
from utils import ErrorResponse
from services.extractor import OpenAIExtractorSingle, run
from pydantic import BaseModel, Field, validator

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_TEXT_LENGTH = 5000

class ExtractionRequest(BaseModel):

    apikey: str = Field(
        ...,
        description="API key for authentication",
        example="1234567890"
    )

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
                "text": "John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567",
                "fields": ["name", "address", "phone"]
            }
        }

class ExtractedData(BaseModel):
    """Model for successful extraction results"""
    message: str = Field(..., example="Data extracted successfully")
    data: Dict[str, Optional[Union[str, int, float, List[Union[str, int, float]]]]] = Field(
        ...,
        description="Extracted data with field names as keys and extracted values or null. Values can be strings, integers, floats, or lists of these types.",
        example={
            "name": ["John Doe", "Jane Smith"],
            "address": ["123 Main St, New York", "456 Oak Ave, Chicago"],
            "phone": ["(555) 123-4567", "(555) 987-6543"],
            "quantity": [3, 5],
            "amount": [270.00, 150.00]
        }
    )



@router.post(
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
    logger.info(f"Extraction request: {req}")
    start_time = time.time()  # Start timing the request

    """
    Extract structured data from unstructured text.
    
    Parameters:
    - **text**: The input text to extract data from
    - **fields**: Either a list of field names or a dictionary mapping aliases to field names
    """

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

    try:
      
        result = run(req.text, req.fields)
        
        # Calculate response time
        response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
        
        if "error" in result:
            # Log failed attempt
            await log_api_usage(
                user_id=user.get("id"),
                endpoint="/extract",
                status="error",
                response_time=response_time
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Extraction failed",
                    "error": result["error"],
                    "details": result.get("details", None)
                }
            )
        
        # Log successful attempt
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/extract",
            status="success",
            response_time=response_time
        )
        
        logger.info(f"Data extracted successfully: {result}")
        return {
            "message": "Data extracted successfully",
            "data": result
        }
        
    except ValueError as e:
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/extract",
            status="error",
            response_time=int((time.time() - start_time) * 1000)
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await log_api_usage(
            user_id=user.get("id"),
            endpoint="/extract",
            status="error",
            response_time=int((time.time() - start_time) * 1000)
        )
        logger.error(f"Unexpected error during extraction: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during extraction"
        )