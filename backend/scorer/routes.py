import logging
import time
from functools import wraps
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from .gemini_service import score_paper_with_gemini
from .utils import parse_gemini_csv_to_json

logging.basicConfig(level=logging.INFO)

main_blueprint = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'pdf'}

# Simple in-memory rate limiting (use Redis in production)
rate_limit_store = {}
RATE_LIMIT_WINDOW = 24 * 60 * 60  # 24 hours in seconds
MAX_REQUESTS_PER_WINDOW = 9999


def get_client_ip():
    """Extract client IP from request, handling proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'


def check_rate_limit(ip: str) -> dict:
    """
    Check if the client has exceeded the rate limit.
    
    Returns:
        dict with 'allowed' (bool), 'remaining' (int), and optionally 'reset_time' (float)
    """
    now = time.time()
    
    if ip not in rate_limit_store:
        rate_limit_store[ip] = {'count': 1, 'first_request': now}
        return {'allowed': True, 'remaining': MAX_REQUESTS_PER_WINDOW - 1}
    
    record = rate_limit_store[ip]
    
    # Reset if window has passed
    if now - record['first_request'] > RATE_LIMIT_WINDOW:
        rate_limit_store[ip] = {'count': 1, 'first_request': now}
        return {'allowed': True, 'remaining': MAX_REQUESTS_PER_WINDOW - 1}
    
    # Check if under limit
    if record['count'] < MAX_REQUESTS_PER_WINDOW:
        record['count'] += 1
        return {'allowed': True, 'remaining': MAX_REQUESTS_PER_WINDOW - record['count']}
    
    # Rate limit exceeded
    reset_time = record['first_request'] + RATE_LIMIT_WINDOW
    return {
        'allowed': False, 
        'remaining': 0,
        'reset_time': reset_time
    }


def rate_limit(f):
    """Decorator to apply rate limiting to a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = get_client_ip()
        limit_check = check_rate_limit(client_ip)
        
        if not limit_check['allowed']:
            reset_time = time.strftime(
                '%Y-%m-%d %H:%M:%S UTC', 
                time.gmtime(limit_check['reset_time'])
            )
            logging.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify({
                "error": "Rate limit exceeded. You can analyze 1 paper per day.",
                "reset_time": reset_time
            }), 429
        
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename: str) -> bool:
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main_blueprint.route('/api/score-paper', methods=['POST'])
@rate_limit
def handle_score_paper():
    """
    Handle paper scoring requests.
    
    Expects a multipart form with a 'paper' file field containing a PDF.
    Returns JSON with scoring results or an error message.
    """
    # Validate file presence
    if 'paper' not in request.files:
        logging.warning("API call failed: No file part in request.")
        return jsonify({"error": "No paper file provided in the request."}), 400

    paper_file = request.files['paper']

    if paper_file.filename == '':
        logging.warning("API call failed: No file selected.")
        return jsonify({"error": "No file selected for upload."}), 400

    if not allowed_file(paper_file.filename):
        logging.warning(f"API call failed: Invalid file type '{paper_file.filename}'.")
        return jsonify({"error": "Invalid file type. Please upload a PDF."}), 400

    try:
        filename = secure_filename(paper_file.filename)
        logging.info(f"Processing file: {filename}")
        
        # Call Gemini API for scoring
        raw_csv_response = score_paper_with_gemini(paper_file)
        
        # Parse CSV response to JSON
        json_results = parse_gemini_csv_to_json(raw_csv_response)
        
        logging.info("Successfully scored paper and parsed results.")
        return jsonify({
            "success": True, 
            "data": json_results,
            "filename": filename
        })

    except ValueError as e:
        logging.error(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({
            "error": "An internal error occurred while processing the paper. Please try again."
        }), 500


@main_blueprint.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for monitoring."""
    return jsonify({"status": "healthy", "service": "llmri"})
