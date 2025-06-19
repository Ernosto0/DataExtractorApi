from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils import DataExtractor, OpenAIExtractor
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExtractionRequest(BaseModel):
    text: str
    fields: list[str]

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

    if not req.text:
        raise HTTPException(status_code=400, detail="No text provided.")    

    result = {}

    data_extractor = DataExtractor(req.text)
    data_extractor.extract_data()
    openai_extractor = OpenAIExtractor({"text": req.text}, fields=req.fields)
        
    result = openai_extractor.openai_api_call()
    
    logger.info(f"Data extracted successfully: {result}")

    return {"message": "Data extracted successfully", "data": result}
   
    


