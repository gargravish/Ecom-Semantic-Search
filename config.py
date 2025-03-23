import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-production'
    
    # Google Cloud configuration
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'raves-altostrat')
    VERTEX_AI_LOCATION = os.getenv('VERTEX_AI_LOCATION', 'us-central1')
    
    # Feature Store configuration
    FEATURE_STORE_ID = os.getenv('FEATURE_STORE_ID', 'products_online_feature_store')
    ENTITY_TYPE_ID = os.getenv('ENTITY_TYPE_ID', 'products_feature_view')
    
    # BigQuery configuration
    BIGQUERY_DATASET = os.getenv('BIGQUERY_DATASET', 'raves_us')
    
    # Upload configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app/static/uploads') 