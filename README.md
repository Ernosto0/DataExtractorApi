# Data Extractor API

A FastAPI-based API that uses AI (OpenAI) to extract structured data, classify text, detect field types, and pull multiple records out of unstructured text. Includes a web UI for account, API key, and usage management, plus JWT/session-based authentication, MongoDB-backed usage tracking, and rate limiting.

## Features

- **Extraction** – pull specific fields out of free-form text, with support for custom field aliases
- **Classification** – classify text against a set of labels
- **Multi-record extraction** – extract multiple structured records from a single block of text
- **Type detection** – infer the data type of each requested field (e.g. currency, date, alphanumeric code)
- **Authentication** – user registration/login with JWT access tokens and API keys
- **Usage tracking** – per-user monthly usage limits and history, backed by MongoDB
- **Rate limiting** – IP-based rate limiting (10 requests/minute) via `slowapi`
- **Web dashboard** – simple HTML pages for login, registration, API key management, and usage stats

## Requirements

- Python 3.10+
- A MongoDB instance (local or hosted)
- An OpenAI API key

## Setup

1. Create and activate a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\activate  # On Windows
source venv/bin/activate  # On Unix/MacOS
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables (see below), e.g. by creating a `.env` file in the project root:
```bash
OPENAI_API_KEY=sk-...
MONGO_URI=mongodb://localhost:27017
SECRET_KEY=change-me
REQUIRE_API_KEY=true
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. Used by the extraction, classification, multi-extraction, and type detection services to call OpenAI. |
| `MONGO_URI` | `mongodb://localhost:27017` | Connection string for the MongoDB instance used to store users and API usage. |
| `SECRET_KEY` | `your-secret-key-here` | Secret used to sign JWT access tokens. Set a strong value in production. |
| `REQUIRE_API_KEY` | `true` | When `true`, the `/api/extract` endpoint requires a valid API key. When `false`, it falls back to IP-based rate limiting only (useful for public testing). |
| `ENABLE_PROVIDER_VERIFICATION` | `false` | Enables verification of API marketplace provider headers (e.g. Zyla, RapidAPI). |
| `ZYLA_SECRET_KEY` / `RAPIDAPI_SECRET_KEY` / `OPENAPI_SECRET_KEY` | — | Provider-specific secrets used when provider verification is enabled. |

## Running the Application

To run the application in development mode:

```bash
uvicorn main:app --reload
```

The API and web UI will be available at `http://localhost:8000`.

## API Documentation

Once the application is running, you can access:
- Interactive API documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative API documentation (ReDoc): `http://localhost:8000/redoc`

## Available Endpoints

### Web
- `GET /`: Home page
- `GET /login`, `POST /login`: Web login
- `GET /register`, `POST /register`: Web registration
- `GET /logout`: Log out and clear the session
- `GET /apikeys`, `POST /apikeys/regenerate`: View and regenerate your API key
- `GET /usage`: View usage statistics

### API
- `POST /api/extract`: Extract structured data from unstructured text
- `POST /api/classify`: Classify text against a set of labels
- `POST /api/multi-extract`: Extract multiple records from a single block of text
- `POST /api/detect-type`: Detect the data type of requested fields

Most API endpoints accept an `apikey` field in the request body for authentication (obtain one by registering via the web UI). The `/api/extract` endpoint can run without an API key when `REQUIRE_API_KEY=false`.

## Testing

```bash
pytest
```

## Project Structure

```
api/            # FastAPI route definitions for each endpoint
services/       # Business logic that calls OpenAI for extraction/classification/etc.
templates/      # Jinja2 templates for the web UI
static/         # CSS, JS, and image assets for the web UI
tests/          # Test suite
auth.py         # User auth, JWT, and password hashing
database.py     # MongoDB connection and helpers
security.py     # Marketplace provider verification middleware
main.py         # FastAPI app setup and web routes
```
