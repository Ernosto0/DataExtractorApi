from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Union
from services.multi_record_extractor import run as multi_extract_run
from pydantic import BaseModel, Field, validator

router = APIRouter()

MAX_TEXT_LENGTH = 5000


class MultiExtractRequest(BaseModel):
    apikey: Optional[str] = Field(
        None,
        title="API Key",
        description="Your API key for authentication. Required in production mode (REQUIRE_API_KEY=true), optional in testing mode (REQUIRE_API_KEY=false).",
        example="1234567890"
    )

    text: str = Field(
        ...,
        description="The text to extract information from",
        example="John sent $50 to Alice. Bob sent $40 to Sarah. Chris owes $80 to Megan."
    )
    
    fields: Optional[Union[List[str], Dict[str, str], str]] = Field(
        None,
        description="Optional fields to extract from each record. Can be a list of field names, a dictionary mapping aliases to field names, or a single field name as a string.",
        example=["sender", "amount", "recipient"]
    )

    @validator('text')
    def text_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()
    
    # @validator('apikey')
    # def apikey_must_not_be_empty(cls, v):
    #     if v and not v.strip():
    #         raise ValueError('API key cannot be empty')
    #     return v.strip() if v else v
    
    
    @validator('text')
    def text_must_be_less_than_characters(cls, v):
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f'Text cannot be more than {MAX_TEXT_LENGTH} characters')
        return v

    class Config:
        schema_extra = {
            "example": {
                "text": "John sent $50 to Alice. Bob sent $40 to Sarah. Chris owes $80 to Megan.",
                "fields": ["sender", "amount", "recipient"]
            }
        }

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

    result = multi_extract_run(request.text, request.fields)

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {result.get('details', 'Unknown error')}"
        )

    return {
        "message": "Records extracted successfully",
        "data": result
    } 