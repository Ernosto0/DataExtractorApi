from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils import DataExtractor, OpenAIExtractor
from pydantic import BaseModel, Field, validator
from typing import Union, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExtractionRequest(BaseModel):
    text: str = Field(..., description="The text to extract information from")
    fields: Union[List[str], Dict[str, str]] = Field(
        ..., 
        description="Fields to extract. Can be either a list of field names or a map of alias:field_name"
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

app = FastAPI(
    title="Data Extractor API",
    description="API for extracting and processing data",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
async def root():
    return {"message": "Welcome to Data Extractor API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 

@app.post("/extract")
async def extract_data(req: ExtractionRequest):
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
   
    


