import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("config/.env")

_client: MongoClient | None = None


def get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        _client = MongoClient(uri)
    db_name = os.getenv("MONGODB_DB_NAME", "auto_trader")
    return _client[db_name]
