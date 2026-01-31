"""
routes_sse.py

Server-Sent Events (SSE) routes for real-time progress updates.
Includes Supabase analytics and hidden admin endpoints.
"""

import os
import logging
import time
import json
import queue
import threading
import tempfile
from functools import wraps
from flask import Blueprint, request, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename

from .gemini_service_streaming import score_paper_with_progress
from .gemini_service_high_accuracy_streaming import score_paper_high_accuracy_with_progress
from .utils import parse_gemini_csv_to_json
from .analytics import track_analysis, get_stats, get_recent_requests

logging.basicConfig(level=logging.INFO)

sse_blueprint = Blueprint('sse', __name__)

ALLOWED_EXTENSIONS = {'pdf'}

# Store for progress queues (keyed by request ID)
progress_queues = {}

# Rate limiting
rate_limit_store = {}
RATE_LIMIT_WINDOW = 24 * 60 * 60  # 24 hours
MAX_REQUESTS_PER_WINDOW = 2

# Admin secret key (set via environment variable)
ADMIN_SECRET = os.environ.get('LLMRI_ADMIN_SECRET', 'change-me-in-production')


def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'


def check_rate_limit(ip: str) -> dict:
    now = time.time()
    if ip not in rate_limit_store:
        rate_limit_store[ip] = {'count': 1, 'first_request': now}
        return {'allowed': True, 'remaining': MAX_REQUESTS_PER_WINDOW - 1}
    
    record = rate_limit_store[ip]
    if now - record['first_request'] > RATE_LIMIT_WINDOW:
        rate_limit_store[ip] = {'count': 1, 'first_request': now}
        return {'allowed': True, 'remaining': MAX_REQUESTS_PER_WINDOW - 1}
    
    if record['count'] < MAX_REQUESTS_PER_WINDOW:
        record['count'] += 1
        return {'allowed': True, 'remaining': MAX_REQUESTS_PER_WINDOW - record['count']}
    
    return {'allowed': False, 'remaining': 0}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def send_progress(request_id: str, event_type: str, data: dict):
    """Send a progress event to the client."""
    if request_id in progress_queues:
        progress_queues[request_id].put({
            'event': event_type,
            'data': data
        })


@sse_blueprint.route('/api/score-paper-stream', methods=['POST'])
def handle_score_paper_stream():
    """
    Streaming endpoint for paper scoring with real-time progress.
    Returns Server-Sent Events.
    """
    # Rate limit check
    client_ip = get_client_ip()
    limit_check = check_rate_limit(client_ip)
    if not limit_check['allowed']:
        return jsonify({
            "error": "You've used your daily max, try again tomorrow! We're hoping to up our limit soon; in the meantime, please consider donating. Every dollar = 20+ papers analyzed!",
            "rate_limited": True
        }), 429

    # Validate file
    if 'paper' not in request.files:
        return jsonify({"error": "No paper file provided"}), 400

    paper_file = request.files['paper']
    if paper_file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(paper_file.filename):
        return jsonify({"error": "Invalid file type. Please upload a PDF."}), 400

    mode = request.form.get('mode', 'standard')
    filename = secure_filename(paper_file.filename)
    
    # Generate unique request ID
    request_id = f"{client_ip}-{int(time.time() * 1000)}"
    
    # Create progress queue
    progress_queues[request_id] = queue.Queue()
    
    # Save file to disk BEFORE starting thread
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, filename)
    
    try:
        paper_file.stream.seek(0)
    except (AttributeError, ValueError):
        pass
    
    paper_file.save(temp_file_path)
    logging.info(f"Saved uploaded file to: {temp_file_path}")

    def generate():
        analysis_success = False
        start_time = time.time()
        
        try:
            # Send initial event
            yield f"data: {json.dumps({'event': 'start', 'data': {'mode': mode, 'filename': filename}})}\n\n"

            # Start analysis in background thread
            result_holder = {'result': None, 'error': None}
            
            def run_analysis():
                try:
                    if mode == 'high-accuracy':
                        result_holder['result'] = score_paper_high_accuracy_with_progress(
                            temp_file_path,
                            lambda evt, data: send_progress(request_id, evt, data)
                        )
                    else:
                        result_holder['result'] = score_paper_with_progress(
                            temp_file_path,
                            lambda evt, data: send_progress(request_id, evt, data)
                        )
                except Exception as e:
                    result_holder['error'] = str(e)
                    send_progress(request_id, 'error', {'message': str(e)})
                finally:
                    send_progress(request_id, 'done', {})
                    # Cleanup temp file
                    try:
                        os.remove(temp_file_path)
                        os.rmdir(temp_dir)
                    except Exception as cleanup_error:
                        logging.warning(f"Failed to cleanup temp file: {cleanup_error}")

            thread = threading.Thread(target=run_analysis)
            thread.start()

            # Stream progress events
            while True:
                try:
                    event = progress_queues[request_id].get(timeout=1)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    if event['event'] == 'done':
                        break
                    if event['event'] == 'error':
                        break
                except queue.Empty:
                    # Send keepalive
                    yield f": keepalive\n\n"
                    if not thread.is_alive():
                        break

            thread.join()

            # Calculate processing time
            processing_time = round(time.time() - start_time, 2)

            # Send final result
            if result_holder['error']:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': result_holder['error']}})}\n\n"
            elif result_holder['result']:
                nonlocal analysis_success
                analysis_success = True
                metadata = result_holder['result'].get('metadata', {})
                raw_csv = result_holder['result'].get('csv', '')
                json_results = parse_gemini_csv_to_json(raw_csv)
                
                yield f"data: {json.dumps({'event': 'complete', 'data': {'success': True, 'results': json_results, 'metadata': metadata, 'filename': filename, 'mode': mode}})}\n\n"

        finally:
            # Track analytics to Supabase
            processing_time = round(time.time() - start_time, 2)
            try:
                track_analysis(
                    mode=mode,
                    client_ip=client_ip,
                    success=analysis_success,
                    processing_time=processing_time,
                    filename=filename
                )
            except Exception as e:
                logging.error(f"Failed to track analytics: {e}")
            
            # Cleanup queue
            if request_id in progress_queues:
                del progress_queues[request_id]

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# =============================================================================
# Hidden Admin Analytics Endpoints
# =============================================================================

@sse_blueprint.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    """
    Hidden analytics endpoint.
    
    Access: /api/admin/stats?key=YOUR_ADMIN_SECRET
    """
    provided_key = request.args.get('key', '')
    if provided_key != ADMIN_SECRET:
        return jsonify({"error": "Not found"}), 404
    
    stats = get_stats()
    return jsonify(stats)


@sse_blueprint.route('/api/admin/requests', methods=['GET'])
def admin_requests():
    """
    View recent requests.
    
    Access: /api/admin/requests?key=YOUR_ADMIN_SECRET&limit=50
    """
    provided_key = request.args.get('key', '')
    if provided_key != ADMIN_SECRET:
        return jsonify({"error": "Not found"}), 404
    
    limit = request.args.get('limit', 50, type=int)
    requests_list = get_recent_requests(limit)
    return jsonify({'requests': requests_list, 'count': len(requests_list)})


@sse_blueprint.route('/api/admin/reset-rate-limit', methods=['POST'])
def admin_reset_rate_limit():
    """
    Reset rate limit for a specific IP.
    
    Access: POST /api/admin/reset-rate-limit?key=YOUR_ADMIN_SECRET&ip=1.2.3.4
    """
    provided_key = request.args.get('key', '')
    if provided_key != ADMIN_SECRET:
        return jsonify({"error": "Not found"}), 404
    
    ip_to_reset = request.args.get('ip', '')
    if not ip_to_reset:
        return jsonify({"error": "No IP provided"}), 400
    
    if ip_to_reset in rate_limit_store:
        del rate_limit_store[ip_to_reset]
        return jsonify({"success": True, "message": f"Rate limit reset for {ip_to_reset}"})
    
    return jsonify({"success": True, "message": f"No rate limit found for {ip_to_reset}"})