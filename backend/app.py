import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from flask_cors import CORS
from scorer.routes import main_blueprint
from scorer.routes_sse import sse_blueprint # <-- 1. ADD THIS IMPORT

def create_app():
    app = Flask(__name__, static_folder='../frontend', static_url_path='/')
    
    # Prevent TypeError by disabling automatic key sorting
    app.config['JSON_SORT_KEYS'] = False
    
    # Configure max upload size (20MB)
    app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
    
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    app.register_blueprint(main_blueprint)
    app.register_blueprint(sse_blueprint) # <-- 2. ADD THIS LINE TO REGISTER IT

    @app.route('/')
    def index():
        return app.send_static_file('index.html')

    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app = create_app()
    app.run(host='0.0.0.0', port=port, debug=True)