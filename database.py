from pymongo import MongoClient
from dotenv import load_dotenv
import os
import secrets

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client.data_extractor_db

# Collections
users = db.users

# Create indexes
users.create_index("email", unique=True)
users.create_index("api_key", unique=True, sparse=True)

def generate_api_key():
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)

def get_next_user_id():
    """Get the next available user ID"""
    # Find the highest current ID and increment by 1
    result = users.find_one(sort=[("id", -1)])
    return 1 if result is None else result["id"] + 1

# Initialize counter if not exists
if users.count_documents({}) == 0:
    # Create a dummy document to start the ID sequence
    users.insert_one({
        "id": 0,
        "email": "system",
        "password_hash": "none",
        "api_key": "none",
        "is_api_key_active": False,
        "usage_limit": 0
    })
    users.delete_one({"id": 0})  # Remove the dummy document 