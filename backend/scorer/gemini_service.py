import os
import pathlib
import logging
import tempfile
import google.generativeai as genai

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configure Gemini API on module load
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not found.")
    genai.configure(api_key=api_key)
    logging.info("Gemini API configured successfully.")
except (ValueError, AttributeError) as e:
    logging.fatal(f"FATAL ERROR: Could not configure Gemini API. {e}")
    # Don't exit - let the app start but fail gracefully on requests


def score_paper_with_gemini(paper_file) -> str:
    """
    Sends a paper to Gemini for COBIDAS scoring.
    
    Args:
        paper_file: A Flask FileStorage object containing the uploaded PDF.
        
    Returns:
        A CSV-formatted string with the scoring results.
        
    Raises:
        ValueError: If the API returns an empty or blocked response.
        Exception: For other API or processing errors.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Save uploaded file temporarily
            temp_path = os.path.join(temp_dir, paper_file.filename)
            paper_file.save(temp_path)
            logging.info(f"Temporarily saved uploaded file to: {temp_path}")

            # Load prompt and rubric
            current_dir = pathlib.Path(__file__).parent.parent
            prompt_path = current_dir / "prompts" / "gemini_prompt.md"
            rubric_path = current_dir / "rubrics" / "cobidas_rubric.csv"

            logging.info(f"Loading prompt from: {prompt_path}")
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_instructions = f.read()

            logging.info(f"Loading rubric from: {rubric_path}")
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_content = f.read()

            # Initialize model
            model_name = 'gemini-2.5-pro'
            model = genai.GenerativeModel(model_name)
            logging.info(f"Initialized Gemini model: {model_name}")

            # Upload PDF to Gemini
            logging.info(f"Uploading file '{paper_file.filename}' to Gemini API...")
            uploaded_file = genai.upload_file(
                path=temp_path,
                display_name=paper_file.filename,
                mime_type='application/pdf'
            )
            logging.info(f"File uploaded successfully. Display name: {uploaded_file.display_name}")

            # Construct the full prompt
            full_prompt = [
                prompt_instructions,
                "\n--- START OF RUBRIC ---\n",
                rubric_content,
                "\n--- END OF RUBRIC ---\n",
                "\n--- START OF PAPER TO EVALUATE ---\n",
                uploaded_file,
                "\n--- END OF PAPER TO EVALUATE ---\n"
            ]

            # Call Gemini API
            logging.info("Sending request to Gemini API. This may take a few minutes...")
            response = model.generate_content(
                full_prompt, 
                request_options={"timeout": 600}
            )
            
            logging.info("Response received from Gemini API.")
            
            # Extract and clean response
            if response.parts:
                raw_text = response.text
                cleaned_text = raw_text.strip()
                
                # Remove markdown code fences if present
                if cleaned_text.startswith("```csv"):
                    cleaned_text = cleaned_text[6:]
                elif cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                
                logging.info("Successfully extracted and cleaned response text.")
                return cleaned_text.strip()
            else:
                # Handle blocked or empty response
                finish_reason = "UNKNOWN"
                if response.prompt_feedback:
                    finish_reason = getattr(
                        response.prompt_feedback.block_reason, 
                        'name', 
                        'UNKNOWN'
                    )
                error_message = f"Received an empty response. Finish Reason: {finish_reason}"
                logging.error(f"Error details: {response.prompt_feedback}")
                raise ValueError(error_message)
                
        except Exception as e:
            logging.error(
                f"An unexpected error occurred during the Gemini API call: {e}", 
                exc_info=True
            )
            raise
