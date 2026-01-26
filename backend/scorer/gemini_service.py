import os
import pathlib
import logging
import tempfile
import json
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


def score_paper_with_gemini(paper_file) -> dict:
    """
    Sends a paper to Gemini for COBIDAS scoring.
    
    Args:
        paper_file: A Flask FileStorage object containing the uploaded PDF.
        
    Returns:
        A dict with 'metadata' (title, authors, year) and 'csv' (scoring results).
        
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

            # Construct prompt - single text block + file
            full_prompt_text = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT: Your response must be in the following JSON format:
{{
  "metadata": {{
    "title": "The full title of the paper",
    "authors": "First Author, Second Author, Third Author, et al.",
    "year": "2024"
  }},
  "csv": "Question_Number,Status,Section,Question_Text,Maximum_Score,ai_score,evidence
1,Mandatory,\\"Experimental Design Reporting\\",\\"Question text here\\",2,2,\\"Evidence here\\"
..."
}}

CRITICAL REQUIREMENTS:
1. Extract the paper's title, authors (abbreviated with et al. if more than 3), and publication year
2. The "csv" field must contain the complete CSV with all 82 rubric items scored
3. Every CSV row MUST have ai_score (number or "N/A") and evidence columns
4. Output ONLY valid JSON - no markdown, no code fences, no extra text
5. Escape quotes properly in the CSV string (use \\" for quotes within the JSON string)

Now analyze the attached PDF paper and output the JSON response:"""

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
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                elif cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                
                cleaned_text = cleaned_text.strip()
                
                # Debug logging
                logging.info(f"Raw response (first 500 chars): {cleaned_text[:500]}")
                
                # Try to parse as JSON
                try:
                    result = json.loads(cleaned_text)
                    
                    # Validate structure
                    if 'metadata' not in result or 'csv' not in result:
                        raise ValueError("Response missing 'metadata' or 'csv' fields")
                    
                    csv_content = result['csv']
                    
                    # Validate CSV has required columns
                    first_line = csv_content.split('\n')[0] if csv_content else ""
                    if 'ai_score' not in first_line or 'evidence' not in first_line:
                        logging.error(f"Missing required columns! Header: {first_line}")
                        raise ValueError(f"CSV missing required columns. Got header: {first_line}")
                    
                    logging.info(f"Metadata extracted: {result['metadata']}")
                    logging.info(f"CSV header: {first_line}")
                    logging.info("Successfully extracted metadata and CSV.")
                    
                    return result
                    
                except json.JSONDecodeError as e:
                    # Fallback: treat entire response as CSV (backwards compatibility)
                    logging.warning(f"Could not parse as JSON, falling back to CSV-only mode: {e}")
                    
                    # Check if it looks like a CSV
                    if 'Question_Number' in cleaned_text and 'ai_score' in cleaned_text:
                        return {
                            'metadata': {
                                'title': None,
                                'authors': None,
                                'year': None
                            },
                            'csv': cleaned_text
                        }
                    else:
                        raise ValueError(f"Response is neither valid JSON nor CSV: {cleaned_text[:200]}")
                
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