from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from services.multi_record_extractor import MultiRecordExtractor
from pydantic import BaseModel, Field, validator

router = APIRouter()

MAX_TEXT_LENGTH = 1000


class MultiExtractRequest(BaseModel):
    apikey: str = Field(
        ...,
        description="API key for authentication",
        example="1234567890"
    )

    text: str = Field(
        ...,
        description="The text to extract information from",
        example="John sent $50 to Alice. Bob sent $40 to Sarah. Chris owes $80 to Megan."
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

class MultiExtractResponse(BaseModel):
    message: str = Field(..., example="Records extracted successfully")
    data: List[Dict] = Field(..., example=[{"from": "John", "amount": "$50", "to": "Alice"}, {"from": "Bob", "amount": "$40", "to": "Sarah"}, {"from": "Chris", "amount": "$80", "to": "Megan"}])


class ErrorResponse(BaseModel):
    detail: str

@router.post("/multi-extract",
    response_model=MultiExtractResponse,
    responses={
        200: {"model": MultiExtractResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def extract_multiple_records(request: MultiExtractRequest):
    """
    Extract multiple records from unstructured text.
    
    The endpoint processes text containing multiple records and returns them as structured data.
    Each record is extracted and formatted consistently based on the content.
    
    Example input text:
    "John sent $50 to Alice. Bob sent $40 to Sarah. Chris owes $80 to Megan."
    
    Example response:
    {
        "message": "Records extracted successfully",
        "records": [
            {"from": "John", "amount": "$50", "to": "Alice"},
            {"from": "Bob", "amount": "$40", "to": "Sarah"},
            {"from": "Chris", "amount": "$80", "to": "Megan"}
        ]
    }
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    extractor = MultiRecordExtractor()
    result = extractor.extract_records(request.text)

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {result.get('details', 'Unknown error')}"
        )

    return {
        "message": "Records extracted successfully",
        "data": result
    } 