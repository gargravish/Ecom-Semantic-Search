from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os

def create_app():
    # Load environment variables
    load_dotenv()

    app = Flask(__name__, static_folder='static')
    
    # Enable CORS for development
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"]
        }
    })

    # Configure the app
    app.config.update(
        GOOGLE_CLOUD_PROJECT=os.getenv('GOOGLE_CLOUD_PROJECT', 'raves-altostrat'),
        VERTEX_AI_LOCATION=os.getenv('VERTEX_AI_LOCATION', 'us-central1'),
        FEATURE_STORE_ID=os.getenv('FEATURE_STORE_ID', 'products_online_feature_store'),
        ENTITY_TYPE_ID=os.getenv('ENTITY_TYPE_ID', 'products_feature_view'),
        BIGQUERY_DATASET=os.getenv('BIGQUERY_DATASET', 'raves_us'),
        GEMINI_API_KEY=os.getenv('GEMINI_API_KEY')
    )
    
    # Register blueprints
    from .api.routes import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register main route
    @app.route('/')
    def index():
        return render_template('index.html')

    # Serve static files
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)
    
    return app 