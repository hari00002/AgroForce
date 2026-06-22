import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "super_secure_2050_secret_key"
    DATABASE = "database.db"
    UPLOAD_FOLDER = "static/uploads"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB image limit
