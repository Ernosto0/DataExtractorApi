from pymongo import MongoClient
from dotenv import load_dotenv
import os
import secrets
import logging

logger = logging.getLogger(__name__)

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client.data_extractor_db

# Collections
users = db.users
api_usage = db.api_usage  # New collection for tracking API usage

# Create indexes
users.create_index("email", unique=True)
users.create_index("api_key", unique=True, sparse=True)
api_usage.create_index([("user_id", 1), ("timestamp", -1)])  # Index for efficient user-based queries

def generate_api_key():
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)

def get_next_user_id():
    """Get the next available user ID"""
    # Find the highest current ID and increment by 1
    result = users.find_one(sort=[("id", -1)])
    return 1 if result is None else result["id"] + 1

async def log_api_usage(user_id: int, endpoint: str, status: str, response_time: float):
    """Log an API call for a user"""
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    
    try:
        log_entry = {
            "user_id": user_id,
            "endpoint": endpoint,
            "status": status,
            "response_time": response_time,
            "timestamp": datetime.utcnow()
        }
        logger.info(f"Logging API usage: {log_entry}")
        api_usage.insert_one(log_entry)
    except Exception as e:
        logger.error(f"Error logging API usage: {e}")
        raise

async def get_user_usage_stats(user_id: int):
    """Get usage statistics for a user"""
    from datetime import datetime, timedelta
    
    # Get user first to check their usage limit
    user = users.find_one({"id": user_id})
    if user is None:
        logger.error(f"User {user_id} not found in database")
        return None  # Return None if user not found
    
    # Get the user's usage limit
    usage_limit = user.get("usage_limit", 0)
    
    # Calculate the start of the current month
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    
    # Get total calls
    total_calls = api_usage.count_documents({"user_id": user_id})
    
    # Get monthly calls
    monthly_calls = api_usage.count_documents({
        "user_id": user_id,
        "timestamp": {"$gte": start_of_month}
    })
    
    # Calculate remaining quota based on user's limit
    remaining_quota = max(0, usage_limit - monthly_calls)
    
    # Get recent usage history (last 50 calls)
    history = list(api_usage.find(
        {"user_id": user_id},
        {"_id": 0, "user_id": 0}  # Exclude these fields from results
    ).sort("timestamp", -1).limit(50))
    
    return {
        "total_calls": total_calls,
        "monthly_calls": monthly_calls,
        "remaining_quota": remaining_quota,
        "usage_history": history
    }

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