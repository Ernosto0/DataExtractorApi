import openai
import os
import json
from dotenv import load_dotenv
import logging
from pydantic import BaseModel, Field
from typing import Union, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()





        

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

class ValidationErrorResponse(BaseModel):
    """Model for validation error responses"""
    detail: Dict[str, str] = Field(
        ...,
        description="Validation error details with field-specific messages",
        example={
            "message": "Validation failed",
            "errors": {
                "text": "Text cannot be empty or exceed 5000 characters",
                "fields": "At least one field must be specified",
                "apikey": "API key is required when authentication is enabled"
            }
        }
    )

class RateLimitErrorResponse(BaseModel):
    """Model for rate limit error responses"""
    detail: Dict[str, str] = Field(
        ...,
        description="Rate limit error details",
        example={
            "message": "Rate limit exceeded",
            "error": "Too many requests",
            "retry_after": "60 seconds",
            "limit": "10 requests per minute"
        }
    )

class ExtractionErrorResponse(BaseModel):
    """Model for extraction failure responses"""
    detail: Dict[str, str] = Field(
        ...,
        description="Extraction error details",
        example={
            "message": "Extraction failed",
            "error": "AI model failed to process text",
            "details": "Text contains unsupported characters or format",
            "suggestion": "Try simplifying the text or reducing the number of fields"
        }
    )