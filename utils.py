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