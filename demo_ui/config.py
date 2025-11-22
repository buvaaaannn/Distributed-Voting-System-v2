"""Configuration for the voting demo UI."""
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
INGESTION_API_URL = os.getenv('INGESTION_API_URL', 'http://localhost:8000')

# Flask Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# UI Configuration
AUTO_REFRESH_INTERVAL = 5000  # milliseconds
