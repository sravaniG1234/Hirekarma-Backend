from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-jwt-key-change-this-in-production")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

settings = Settings()

# Use environment variable if available (for Aiven)
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)

# Configure the engine with connection pool settings
engine = create_engine(
    DATABASE_URL,
    pool_size=5,  # Default is 5
    max_overflow=10,  # Default is 10
    pool_timeout=30,  # Default is 30 seconds
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_pre_ping=True  # Enable connection health checks
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
