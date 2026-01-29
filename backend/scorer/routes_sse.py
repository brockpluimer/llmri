"""
routes_sse.py

Server-Sent Events (SSE) routes for real-time progress updates.
Add these routes to your existing routes.py or import as a blueprint.
"""

import logging
import time
import json
import queue
import threading
from functools import wraps
from flask import Blueprint, request, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename

from .gemini_service_streaming import score_paper_with_progress
from .gemini_service_high_accuracy_streaming import score_paper_high_accuracy_with_progress
from .utils import parse_gemini_csv_to_json

logging.basicConfig(level=logging.INFO)

sse_blueprint = Blueprint('sse', __name__)

ALLOWED_EXTENSIONS = {'pdf'}

# Store for progress queues (keyed by request ID)
progress_queues = {}

# Rate limiting (reuse from main routes)
rate_limit_store = {}
RATE_LIMIT_WINDOW = 24 * 60 * 60
MAX_REQUESTS_PER_WINDOW = 2


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
    
    # CRITICAL FIX: Save file to disk BEFORE starting thread
    # This prevents "read of closed file" errors when request context closes
    import tempfile
    import os
    
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, filename)
    
    try:
        paper_file.stream.seek(0)
    except (AttributeError, ValueError):
        pass
    
    paper_file.save(temp_file_path)
    logging.info(f"Saved uploaded file to: {temp_file_path}")

    def generate():
        try:
            # Send initial event
            yield f"data: {json.dumps({'event': 'start', 'data': {'mode': mode, 'filename': filename}})}\n\n"

            # Start analysis in background thread
            result_holder = {'result': None, 'error': None}
            
            def run_analysis():
                try:
                    if mode == 'high-accuracy':
                        result_holder['result'] = score_paper_high_accuracy_with_progress(
                            temp_file_path,  # Pass file path, not file object
                            lambda evt, data: send_progress(request_id, evt, data)
                        )
                    else:
                        result_holder['result'] = score_paper_with_progress(
                            temp_file_path,  # Pass file path, not file object
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

            # Send final result
            if result_holder['error']:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': result_holder['error']}})}\n\n"
            elif result_holder['result']:
                metadata = result_holder['result'].get('metadata', {})
                raw_csv = result_holder['result'].get('csv', '')
                json_results = parse_gemini_csv_to_json(raw_csv)
                
                yield f"data: {json.dumps({'event': 'complete', 'data': {'success': True, 'results': json_results, 'metadata': metadata, 'filename': filename, 'mode': mode}})}\n\n"

        finally:
            # Cleanup
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