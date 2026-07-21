"""
gemini_service_streaming.py

Standard mode scoring with SSE progress streaming.
"""
import os
import io
import logging
from .gemini_service import get_model, generate_with_retry, process_pdf_for_gemini, load_rubric_map, reconstruct_full_csv
import pathlib

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
        
        if not prompts:
            raise ValueError("Failed to process PDF or generate prompts.")
        
        # Log which method we're using
        if prompts.get('uploaded_file'):
            logger.info("Using Gemini PDF upload method")
            progress_callback('log', {'level': 'info', 'message': 'PDF uploaded to Gemini successfully'})
        elif paper_text:
            logger.info(f"Using text extraction method. Characters: {len(paper_text)}")
            progress_callback('log', {'level': 'info', 'message': f'PDF processed via text extraction. {len(paper_text)} characters.'})
        
        # Call Gemini API - get full result with metadata
        logger.info("Calling Gemini API for standard scoring...")
        progress_callback('log', {'level': 'info', 'message': 'Analyzing paper with Gemini 3.1 Pro...'})
        
        # Build prompt payload
        model = get_model(temperature=0.0)
        uploaded_file = prompts.get('uploaded_file')
        prompt_text = prompts.get('combined_prompt')
        extracted_text = prompts.get('paper_text')
        
        if uploaded_file:
            prompt_payload = [prompt_text, uploaded_file]
        elif extracted_text:
            prompt_payload = [f"{prompt_text}\n\n--- PAPER TEXT ---\n{extracted_text}"]
        else:
            prompt_payload = [prompt_text]
        
        # Get full JSON response (includes metadata)
        result = generate_with_retry(model, prompt_payload)
        
        if not result:
            raise ValueError("Received an empty response from Gemini API.")
        
        # Extract metadata and CSV from result
        metadata = result.get('metadata', {})
        csv_content = result.get('csv', '')
        
        if not csv_content:
            raise ValueError("Gemini response missing CSV data.")
        
        progress_callback('log', {'level': 'success', 'message': 'Analysis complete.'})
        logger.info("Standard scoring complete.")
        
        # Load rubric map for reconstruction
        current_dir = pathlib.Path(__file__).parent.parent
        rubric_path = current_dir / "rubrics" / "cobidas_rubric.csv"
        rubric_map = load_rubric_map(rubric_path)
        
        # Reconstruct full CSV
        full_result = reconstruct_full_csv({'metadata': metadata, 'csv': csv_content}, rubric_map)
        
        return full_result
        
    except Exception as e:
        logger.error(f"Error in standard paper scoring: {e}", exc_info=True)
        progress_callback('error', {'message': str(e)})
        raise
