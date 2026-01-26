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
            model_name = 'gemini-2.5-flash'
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

            # Construct prompt more like the GUI experience - single text block + file
            full_prompt_text = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT REMINDER: Your output MUST be a CSV with exactly these 7 columns:
Question_Number,Status,Section,Question_Text,Maximum_Score,ai_score,evidence

Every row MUST have ai_score (number or "N/A") and evidence (quoted text or "Information not found.").
Do NOT output anything except the CSV data. No explanations, no markdown code fences.

Now analyze the attached PDF paper and output the complete scored CSV:"""

            full_prompt = [full_prompt_text, uploaded_file]

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
                
                cleaned_text = cleaned_text.strip()
                
                # Debug logging - show what we got
                logging.info(f"Raw CSV response (first 500 chars): {cleaned_text[:500]}")
                logging.info(f"Raw CSV response (last 300 chars): {cleaned_text[-300:]}")
                
                # Validate that we have the required columns
                first_line = cleaned_text.split('\n')[0] if cleaned_text else ""
                logging.info(f"CSV header row: {first_line}")
                
                if 'ai_score' not in first_line or 'evidence' not in first_line:
                    logging.error(f"Missing required columns! Header: {first_line}")
                    raise ValueError(f"Gemini response missing required columns. Got header: {first_line}")
                
                logging.info("Successfully extracted and cleaned response text.")
                return cleaned_text
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