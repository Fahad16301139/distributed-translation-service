"""
Configuration module for the Distributed Translation System
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration class"""
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    
    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'translation_system')
    
    # Translation Configuration
    TRANSLATION_MODEL = os.getenv('TRANSLATION_MODEL', 'Helsinki-NLP/opus-mt-en-de')
    MAX_LENGTH = int(os.getenv('MAX_LENGTH', 512))
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 60))
    RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 1000))
    
    # Circuit Breaker
    CIRCUIT_BREAKER_FAIL_MAX = int(os.getenv('CIRCUIT_BREAKER_FAIL_MAX', 5))
    CIRCUIT_BREAKER_TIMEOUT = int(os.getenv('CIRCUIT_BREAKER_TIMEOUT', 60))
    
    # External API Configuration
    GOOGLE_TRANSLATE_API_KEY = os.getenv('GOOGLE_TRANSLATE_API_KEY', '')
    EXTERNAL_TRANSLATION_API_URL = os.getenv('EXTERNAL_TRANSLATION_API_URL', '')
    
    # Service Ports
    TEXT_INGESTION_PORT = int(os.getenv('TEXT_INGESTION_PORT', 5001))
    TRANSLATION_SERVICE_PORT = int(os.getenv('TRANSLATION_SERVICE_PORT', 5002))
    FEEDBACK_SERVICE_PORT = int(os.getenv('FEEDBACK_SERVICE_PORT', 5003))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


config = Config()

