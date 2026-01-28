# backend/scorer/gemini_service_streaming.py
"""
Standard mode scoring with SSE progress streaming.
"""

import os
import io
import logging
from .gemini_service import get_gemini_response, process_pdf_for_gemini
from .utils import extract_metadata_from_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def score_paper_with_progress(file_path_or_file, progress_callback):
    """
    Scores a paper using the standard Gemini model and provides progress updates.
    
    Args:
        file_path_or_file: Either a file path string or FileStorage object
        progress_callback: Function to call with progress updates
    
    Returns:
        dict with 'csv' and 'metadata' keys
    """
    try:
        progress_callback('upload', {'status': 'processing', 'method': 'Standard'})
        logger.info("Processing PDF for standard analysis...")
        
        # Handle both file paths and file objects
        if isinstance(file_path_or_file, str):
            # It's a file path - create a simple wrapper
            class FileWrapper:
                def __init__(self, path):
                    self.filename = os.path.basename(path)
                    self._path = path
                    with open(path, 'rb') as f:
                        self.stream = io.BytesIO(f.read())
                
                def save(self, dest_path):
                    import shutil
                    shutil.copy(self._path, dest_path)
            
            paper_file = FileWrapper(file_path_or_file)
        else:
            paper_file = file_path_or_file
        
        # Process PDF
        paper_text, prompts = process_pdf_for_gemini(paper_file)
        
        # Only check prompts - paper_text can be empty string when using PDF upload
        if not prompts:
            raise ValueError("Failed to process PDF or generate prompts.")
        
        # Log which method we're using
        if prompts.get('uploaded_file'):
            logger.info("Using Gemini PDF upload method")
            progress_callback('log', {'level': 'info', 'message': 'PDF uploaded to Gemini successfully'})
        elif paper_text:
            logger.info(f"Using text extraction method. Characters: {len(paper_text)}")
            progress_callback('log', {'level': 'info', 'message': f'PDF processed via text extraction. {len(paper_text)} characters.'})
        
        # Call Gemini API
        logger.info("Calling Gemini API for standard scoring...")
        progress_callback('log', {'level': 'info', 'message': 'Analyzing paper with Gemini 2.5 Pro...'})
        
        gemini_result_csv = get_gemini_response(prompts)
        
        if not gemini_result_csv:
            raise ValueError("Received an empty response from Gemini API.")
        
        progress_callback('log', {'level': 'success', 'message': 'Analysis complete.'})
        logger.info("Standard scoring complete.")
        
        # Extract metadata
        metadata = extract_metadata_from_response(gemini_result_csv)
        
        return {
            "csv": gemini_result_csv,
            "metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Error in standard paper scoring: {e}", exc_info=True)
        progress_callback('error', {'message': str(e)})
        raise
