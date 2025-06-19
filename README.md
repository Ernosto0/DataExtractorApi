# Data Extractor API

A FastAPI-based API for data extraction and processing.

## Setup

1. Create and activate a virtual environment (if not already done):
```bash
python -m venv venv
.\venv\Scripts\activate  # On Windows
source venv/bin/activate  # On Unix/MacOS
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

To run the application in development mode:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the application is running, you can access:
- Interactive API documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative API documentation (ReDoc): `http://localhost:8000/redoc`

## Available Endpoints

- `GET /`: Welcome message
- `GET /health`: Health check endpoint 