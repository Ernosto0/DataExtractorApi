from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
from fastapi import HTTPException
import time
import os
from database import users,  log_api_usage
from auth import check_usage_limit, update_usage_limit
from utils import ErrorResponse, ValidationErrorResponse, RateLimitErrorResponse, ExtractionErrorResponse
from services.extractor import OpenAIExtractorSingle, run
from pydantic import BaseModel, Field, validator, root_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiting configuration
limiter = Limiter(key_func=get_remote_address)

# Environment variable to toggle API key requirement
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "true").lower() == "true"

MAX_TEXT_LENGTH = 5000

class ExtractionRequest(BaseModel):
    """Request model for text extraction endpoint"""

    apikey: Optional[str] = Field(
        None,
        title="API Key",
        description="Your API key for authentication. Required in production mode (REQUIRE_API_KEY=true), optional in testing mode (REQUIRE_API_KEY=false).",
        example="1234567890"
    )

    text: str = Field(
        ..., 
        title="Text to Extract From",
        description="The unstructured text to extract information from. Maximum length is 5,000 characters.",
        example="John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567",
        min_length=1,
        max_length=MAX_TEXT_LENGTH
    )
    
    fields: Union[List[str], Dict[str, str], str] = Field(
        ..., 
        title="Fields to Extract",
        description="Fields to extract from the text. Use an array for simple extraction ['name', 'email'], a comma-separated string 'name,address,phone', or an object for custom aliases {'customer_name': 'name', 'contact_email': 'email'}",
        example=["name", "address", "phone"]
    )

    @validator('text')
    def text_must_not_be_empty_and_length_check(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f'Text cannot be more than {MAX_TEXT_LENGTH} characters')
        return v.strip()

    @validator('fields')
    def fields_must_not_be_empty(cls, v):
        # Handle comma-separated string input
        if isinstance(v, str):
            # Split by comma and strip whitespace
            field_list = [field.strip() for field in v.split(',') if field.strip()]
            if not field_list:
                raise ValueError('Fields string cannot be empty and must contain non-empty field names')
            return field_list
        
        if isinstance(v, list) and (not v or not all(v)):
            raise ValueError('Fields list cannot be empty and must contain non-empty strings')
        if isinstance(v, dict) and (not v or not all(v.keys()) or not all(v.values())):
            raise ValueError('Fields map cannot be empty and must contain non-empty strings')
        return v
    
    @validator('apikey')
    def apikey_must_not_be_empty(cls, v):
        if REQUIRE_API_KEY and (not v or not v.strip()):
            raise ValueError('API key is required')
        return v.strip() if v else None
    
    class Config:
        schema_extra = {
            "examples": [
                {
                    "summary": "Array format",
                    "value": {
                        "text": "John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567",
                        "fields": ["name", "address", "phone"]
                    }
                },
                {
                    "summary": "Comma-separated string format",
                    "value": {
                        "text": "John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567",
                        "fields": "name,address,phone"
                    }
                },
                {
                    "summary": "Dictionary format with aliases",
                    "value": {
                        "text": "Customer: Jane Smith, Contact: jane@email.com",
                        "fields": {"customer_name": "name", "contact_email": "email"}
                    }
                }
            ]
        }

class ExtractedData(BaseModel):
    """Model for successful extraction results"""
    message: str = Field(..., example="Data extracted successfully")
    data: Dict[str, Optional[Union[str, int, float, List[Union[str, int, float]]]]] = Field(
        ...,
        description="Extracted data with field names as keys and extracted values or null. Values can be strings, integers, floats, or lists of these types.",
        examples=[
            {
                "name": "John Doe",
                "address": "123 Main St, New York",
                "phone": "(555) 123-4567"
            },
            {
                "invoice_number": "INV-2024-001",
                "amount": 1250.00,
                "company": "Acme Corp",
                "due_date": "2024-02-15"
            },
            {
                "customer_name": "Jane Smith",
                "contact_email": "jane.smith@email.com",
                "order_id": "12345",
                "total_amount": 99.99
            },
            {
                "receipt_number": "R-456789",
                "store_name": "TechStore Inc",
                "items": ["Laptop", "Mouse"],
                "quantities": [2, 1],
                "prices": [800.0, 25.0],
                "subtotal": 1625.0,
                "tax": 130.25,
                "total": 1755.25,
                "customer": "Bob Wilson",
                "phone": "(555) 987-6543",
                "date": "March 15, 2024"
            }
        ]
    )

    class Config:
        schema_extra = {
            "examples": [
                {
                    "summary": "Simple contact extraction",
                    "value": {
                        "message": "Data extracted successfully",
                        "data": {
                            "name": "John Doe",
                            "address": "123 Main St, New York", 
                            "phone": "(555) 123-4567"
                        }
                    }
                },
                {
                    "summary": "Invoice data extraction",
                    "value": {
                        "message": "Data extracted successfully",
                        "data": {
                            "invoice_number": "INV-2024-001",
                            "amount": 1250.00,
                            "company": "Acme Corp",
                            "due_date": "2024-02-15"
                        }
                    }
                },
                {
                    "summary": "Multiple items with lists",
                    "value": {
                        "message": "Data extracted successfully",
                        "data": {
                            "items": ["Laptop", "Mouse", "Keyboard"],
                            "quantities": [2, 1, 1],
                            "prices": [800.0, 25.0, 45.0],
                            "total": 1670.0
                        }
                    }
                },
                {
                    "summary": "Missing fields (null values)",
                    "value": {
                        "message": "Data extracted successfully",
                        "data": {
                            "name": "Alice Johnson",
                            "email": "alice@example.com",
                            "phone": None,
                            "address": None
                        }
                    }
                }
            ]
        }

@router.post(
    "/extract",
    response_model=ExtractedData,
    responses={
        200: {
            "description": "Data extracted successfully",
            "model": ExtractedData,
            "content": {
                "application/json": {
                    "example": {
                        "message": "Data extracted successfully",
                        "data": {
                            "name": "John Doe",
                            "address": "123 Main St, New York",
                            "phone": "(555) 123-4567",
                            "email": "john.doe@email.com"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Validation error - Invalid input parameters",
            "model": ValidationErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "empty_text": {
                            "summary": "Empty text field",
                            "value": {
                                "detail": {
                                    "message": "Validation failed",
                                    "error": "Text cannot be empty",
                                    "field": "text"
                                }
                            }
                        },
                        "text_too_long": {
                            "summary": "Text exceeds maximum length",
                            "value": {
                                "detail": {
                                    "message": "Validation failed",
                                    "error": "Text cannot be more than 5000 characters",
                                    "field": "text",
                                    "current_length": "6245"
                                }
                            }
                        },
                        "no_fields": {
                            "summary": "No fields specified",
                            "value": {
                                "detail": {
                                    "message": "Validation failed",
                                    "error": "At least one field must be specified",
                                    "field": "fields"
                                }
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication error - Invalid or missing API key",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "missing_api_key": {
                            "summary": "Missing API key",
                            "value": {
                                "detail": {
                                    "message": "Authentication required",
                                    "error": "API key is required",
                                    "code": "MISSING_API_KEY"
                                }
                            }
                        },
                        "invalid_api_key": {
                            "summary": "Invalid API key",
                            "value": {
                                "detail": {
                                    "message": "Authentication failed",
                                    "error": "Invalid API key",
                                    "code": "INVALID_API_KEY"
                                }
                            }
                        }
                    }
                }
            }
        },
        402: {
            "description": "Payment required - Usage limit exceeded",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "message": "Usage limit exceeded",
                            "error": "You have reached your monthly API usage limit",
                            "code": "USAGE_LIMIT_EXCEEDED",
                            "suggestion": "Please upgrade your plan or wait for the next billing cycle"
                        }
                    }
                }
            }
        },
        422: {
            "description": "Extraction failed - AI processing error",
            "model": ExtractionErrorResponse,
            "content": {
                "application/json": {
                    "examples": {
                        "ai_processing_error": {
                            "summary": "AI model processing failed",
                            "value": {
                                "detail": {
                                    "message": "Extraction failed",
                                    "error": "AI model failed to process the text",
                                    "code": "AI_PROCESSING_ERROR",
                                    "suggestion": "Try simplifying the text or reducing the number of fields"
                                }
                            }
                        },
                        "invalid_json_response": {
                            "summary": "Invalid AI response format",
                            "value": {
                                "detail": {
                                    "message": "Extraction failed",
                                    "error": "Failed to parse AI response",
                                    "code": "INVALID_AI_RESPONSE",
                                    "suggestion": "Please try again with different text"
                                }
                            }
                        }
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded - Too many requests",
            "model": RateLimitErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "message": "Rate limit exceeded",
                            "error": "Too many requests from your IP address",
                            "code": "RATE_LIMIT_EXCEEDED",
                            "limit": "10 requests per minute",
                            "retry_after": "45 seconds",
                            "suggestion": "Please wait before making another request"
                        }
                    }
                }
            }
        },
        500: {
            "description": "Internal server error - Unexpected system error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "message": "Internal server error",
                            "error": "An unexpected error occurred during extraction",
                            "code": "INTERNAL_ERROR",
                            "suggestion": "Please try again later or contact support if the issue persists"
                        }
                    }
                }
            }
        }
    },
    summary="Extract structured data from unstructured text",
    description="""
    Extract specific fields from unstructured text using AI-powered natural language processing.
    
    ## How it works:
    1. Send your unstructured text and specify which fields you want to extract
    2. The AI analyzes the text and identifies the requested information
    3. Receive structured JSON data with the extracted fields
    
    ## Supported field types:
    - **Text fields**: Names, addresses, descriptions, etc.
    - **Numeric fields**: Amounts, quantities, IDs, etc.
    - **Date fields**: Dates in various formats
    - **Contact info**: Emails, phone numbers, etc.
    - **Lists**: Multiple values of the same type
    
    ## Field mapping:
    - Use a **list** for simple field extraction: `["name", "email", "phone"]`
    - Use a **comma-separated string** for simple field extraction: `"name,email,phone"`
    - Use a **dictionary** for custom aliases: `{"customer_name": "name", "contact_email": "email"}`
    
    ## Text limitations:
    - Maximum text length: **5,000 characters**
    - For longer texts, consider breaking them into smaller chunks
    - Multi-record extraction available for texts with multiple entities
    
    ## Authentication:
    - **API Key mode**: Include your API key in the request (production)
    - **Rate-limited mode**: No API key required (testing/evaluation)
    - Mode is controlled by the `REQUIRE_API_KEY` environment variable
    
    ## Rate limits:
    - **10 requests per minute** per IP address
    - Rate limits apply regardless of authentication mode
    - Upgrade your plan for higher limits
    
    ## Response format:
    - Success responses always include extracted data in the `data` field
    - Missing fields return `null` values
    - Numeric values are returned as numbers, not strings
    - Lists are returned for multiple occurrences of the same field
    """,
    tags=["extraction"]
)
@limiter.limit("10/minute")
async def extract_data(request: Request, req: ExtractionRequest):
    """
    Extract structured data from unstructured text using AI-powered natural language processing.
    
    This endpoint analyzes your text and extracts specific fields you request, returning structured JSON data.
    
    ## Request Body Parameters:
    
    - **text** (string, required): The unstructured text to extract data from
        - Maximum length: 5,000 characters
        - Example: "John Doe lives at 123 Main St, New York and can be reached at (555) 123-4567"
    
    - **fields** (array, string, or object, required): Fields to extract from the text
        - Array format: `["name", "email", "phone"]` for simple field extraction
        - String format: `"name,email,phone"` for comma-separated field extraction
        - Object format: `{"customer_name": "name", "contact_email": "email"}` for custom aliases
        - At least one field must be specified
    
    - **apikey** (string, optional): Your API key for authentication
        - Required when `REQUIRE_API_KEY=true` (production mode)
        - Optional when `REQUIRE_API_KEY=false` (testing/evaluation mode)
        - Example: "your-api-key-here"
    
    ## Field Types Supported:
    - **Text**: Names, addresses, descriptions, IDs
    - **Numbers**: Amounts, quantities, prices (returned as numeric values)
    - **Dates**: Various date formats (returned as strings)
    - **Contact Info**: Emails, phone numbers
    - **Lists**: Multiple values of the same type
    
    ## Response Format:
    Returns a JSON object with:
    - `message`: Success message
    - `data`: Object containing extracted fields with their values
    - Missing or unidentifiable fields return `null`
    - Numeric values are returned as numbers, not strings
    - Multiple values for the same field are returned as arrays
    
    ## Rate Limiting:
    - 10 requests per minute per IP address
    - Additional usage limits may apply based on your plan (in API key mode)
    
    ## Authentication Modes:
    1. **Production Mode** (`REQUIRE_API_KEY=true`): Requires valid API key
    2. **Testing Mode** (`REQUIRE_API_KEY=false`): No API key required, rate limiting only
    
    ## Example Requests:
    
    ### Simple extraction (array format):
    ```json
    {
        "text": "John Doe, email: john@example.com, phone: (555) 123-4567",
        "fields": ["name", "email", "phone"]
    }
    ```
    
    ### Simple extraction (string format):
    ```json
    {
        "text": "John Doe, email: john@example.com, phone: (555) 123-4567",
        "fields": "name,email,phone"
    }
    ```
    
    ### With custom aliases:
    ```json
    {
        "apikey": "your-api-key",
        "text": "Invoice #INV-001 for $1,250.00 from Acme Corp",
        "fields": {
            "invoice_id": "invoice_number",
            "total_amount": "amount",
            "vendor_name": "company"
        }
    }
    ```
    
    ## Example Response:
    ```json
    {
        "message": "Data extracted successfully",
        "data": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "(555) 123-4567"
        }
    }
    ```
    """
    logger.info(f"Extraction request: {req}")
    start_time = time.time()  # Start timing the request

    """
    Extract structured data from unstructured text.
    
    Parameters:
    - **text**: The input text to extract data from
    - **fields**: Either a list of field names or a dictionary mapping aliases to field names
    """

    user = None
    user_identifier = None
    
    if REQUIRE_API_KEY:
        if req.apikey is None:
            raise HTTPException(
                status_code=401, 
                detail={
                    "message": "Authentication required",
                    "error": "API key is required",
                    "code": "MISSING_API_KEY",
                    "suggestion": "Include your API key in the request body"
                }
            )

        user = users.find_one({"api_key": req.apikey})
        if user is None:
            raise HTTPException(
                status_code=401, 
                detail={
                    "message": "Authentication failed",
                    "error": "Invalid API key",
                    "code": "INVALID_API_KEY",
                    "suggestion": "Check your API key or generate a new one"
                }
            )

        # Get user ID, falling back to email if ID is not present
        user_identifier = user.get("id") or user.get("_id") or user.get("email")
        if not user_identifier:
            raise HTTPException(
                status_code=500, 
                detail={
                    "message": "Internal server error",
                    "error": "Invalid user data structure",
                    "code": "INVALID_USER_DATA",
                    "suggestion": "Please contact support if this issue persists"
                }
            )

        if not check_usage_limit(user_identifier):
            raise HTTPException(
                status_code=402, 
                detail={
                    "message": "Usage limit exceeded",
                    "error": "You have reached your monthly API usage limit",
                    "code": "USAGE_LIMIT_EXCEEDED",
                    "suggestion": "Please upgrade your plan or wait for the next billing cycle"
                }
            )

        update_usage_limit(user_identifier, 1)
    else:
        # In rate-limited mode without API keys, use IP address as identifier
        user_identifier = get_remote_address(request)
        logger.info(f"Rate-limited mode: using IP {user_identifier} as identifier")

    try:
        # Validate text length before processing
        if len(req.text) > MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Validation failed",
                    "error": f"Text cannot be more than {MAX_TEXT_LENGTH} characters",
                    "field": "text",
                    "current_length": str(len(req.text)),
                    "code": "TEXT_TOO_LONG"
                }
            )
        
        # Validate fields
        if isinstance(req.fields, list) and len(req.fields) == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Validation failed",
                    "error": "At least one field must be specified",
                    "field": "fields",
                    "code": "NO_FIELDS_SPECIFIED"
                }
            )
  
        result = run(req.text, req.fields)
    
        # Calculate response time
        response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
    
        if "error" in result:
            # Log failed attempt (only if user exists)
            if user:
                await log_api_usage(
                    user_id=user.get("id"),
                    endpoint="/extract",
                    status="error",
                    response_time=response_time
                )
            
            # Determine error type based on the error content
            error_details = result.get("details", "")
            if "parse" in result["error"].lower() or "json" in result["error"].lower():
                error_code = "INVALID_AI_RESPONSE"
                suggestion = "Please try again with different text or contact support"
            elif "timeout" in result["error"].lower():
                error_code = "AI_TIMEOUT"
                suggestion = "The request timed out. Try with shorter text or fewer fields"
            else:
                error_code = "AI_PROCESSING_ERROR"
                suggestion = "Try simplifying the text or reducing the number of fields"
            
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Extraction failed",
                    "error": result["error"],
                    "details": error_details,
                    "code": error_code,
                    "suggestion": suggestion
                }
            )
    
        # Log successful attempt (only if user exists)
        if user:
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
        if user:
            await log_api_usage(
                user_id=user.get("id"),
                endpoint="/extract",
                status="error",
                response_time=int((time.time() - start_time) * 1000)
            )
        raise HTTPException(
            status_code=400, 
            detail={
                "message": "Validation failed",
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "suggestion": "Check your input parameters and try again"
            }
        )
    except Exception as e:
        if user:
            await log_api_usage(
                user_id=user.get("id"),
                endpoint="/extract",
                status="error",
                response_time=int((time.time() - start_time) * 1000)
            )
        logger.error(f"Unexpected error during extraction: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "error": "An unexpected error occurred during extraction",
                "code": "INTERNAL_ERROR",
                "suggestion": "Please try again later or contact support if the issue persists"
            }
        )