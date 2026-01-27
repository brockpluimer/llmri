import os
import pathlib
import logging
import tempfile
import json
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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
    Sends a paper to Gemini 2.5 Pro for COBIDAS scoring with strict deterministic settings.
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

            # --- 1. STRICT GENERATION CONFIG (Determinism & Format) ---
            generation_config = {
                "temperature": 0.0,
                "top_p": 0.95,
                "top_k": 1,  # Force greedy decoding (reduces variability)
                "max_output_tokens": 8192,
                "response_mime_type": "application/json",  # Force JSON output
            }

            # --- 2. DISABLE SAFETY FILTERS (Prevent Blank/Blocked Responses) ---
            # Scientific papers often contain medical/crime terms that trigger false positives
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            # Initialize model
            model_name = 'gemini-2.5-pro' 
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            logging.info(f"Initialized Gemini model: {model_name} with safety filters disabled.")

            # Upload PDF to Gemini
            logging.info(f"Uploading file '{paper_file.filename}' to Gemini API...")
            uploaded_file = genai.upload_file(
                path=temp_path,
                display_name=paper_file.filename,
                mime_type='application/pdf'
            )
            logging.info(f"File uploaded successfully. Display name: {uploaded_file.display_name}")

            # Construct prompt
            full_prompt_text = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT: Return the result strictly as JSON obeying this structure:
{{
  "metadata": {{
    "title": "Paper Title",
    "authors": "Author Names",
    "year": "2024"
  }},
  "csv": "Question_Number,Status,Section,Question_Text,Maximum_Score,ai_score,evidence\\n..."
}}
"""

            full_prompt = [full_prompt_text, uploaded_file]

            # Call Gemini API
            logging.info("Sending request to Gemini API...")
            response = model.generate_content(
                full_prompt, 
                request_options={"timeout": 600}
            )
            
            logging.info("Response received from Gemini API.")
            
            # --- 3. ROBUST PARSING ---
            if response.parts:
                cleaned_text = response.text.strip()
                logging.info(f"Raw response preview: {cleaned_text[:200]}")
                
                try:
                    result = json.loads(cleaned_text)
                    
                    # Validate keys
                    if 'metadata' not in result or 'csv' not in result:
                        raise ValueError("Response missing 'metadata' or 'csv' fields")
                    
                    # Quick check on CSV integrity
                    if not result['csv'].strip():
                         raise ValueError("CSV field is empty")

                    return result
                    
                except json.JSONDecodeError as e:
                    logging.error(f"JSON Decode Error: {e}")
                    logging.error(f"Failed JSON text: {cleaned_text}")
                    raise ValueError(f"Model did not return valid JSON: {e}")
            else:
                # Specific logging for safety blocks if they still happen
                feedback = response.prompt_feedback
                logging.error(f"Blocked Response Details: {feedback}")
                raise ValueError(f"Gemini refused to process the file. Reason: {feedback}")

        except Exception as e:
            logging.error(f"Error in gemini_service: {e}", exc_info=True)
            raise