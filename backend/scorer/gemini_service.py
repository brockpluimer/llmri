"""
gemini_service.py - UPDATED VERSION WITH STREAMING COMPATIBILITY

This version includes compatibility functions for gemini_service_streaming.py
while maintaining the new structure.
"""

import os
import pathlib
import logging
import tempfile
import json
import csv
import io
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from pypdf import PdfReader

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configure Gemini API
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not found.")
    genai.configure(api_key=api_key)
except Exception as e:
    logging.fatal(f"FATAL ERROR: Could not configure Gemini API. {e}")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Fallback method: Extracts raw text if Gemini blocks the PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logging.error(f"Failed to extract text from PDF: {e}")
        return ""


def load_rubric_map(rubric_path):
    """
    Loads the rubric CSV into a dictionary for fast lookup.
    Keys are Question_Number (string).
    """
    rubric_map = {}
    try:
        # utf-8-sig automatically handles Byte Order Marks (BOM) if present
        with open(rubric_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            
            # Verify headers match what we expect
            if 'Question_Number' not in reader.fieldnames:
                logging.error(f"Rubric CSV is missing 'Question_Number'. Found: {reader.fieldnames}")
                return {}

            for row in reader:
                # normalize ID to remove potential whitespace
                q_id = row.get('Question_Number', '').strip()
                if q_id:
                    rubric_map[q_id] = {
                        'Status': row.get('Status', 'Mandatory'),
                        'Section': row.get('Section', 'Unknown Section'),
                        'Question_Text': row.get('Question_Text', 'Unknown Question'),
                        'Maximum_Score': row.get('Maximum_Score', '0')
                    }
    except Exception as e:
        logging.error(f"Failed to load rubric file: {e}")
        
    logging.info(f"Successfully loaded {len(rubric_map)} rubric items.")
    return rubric_map


def get_model(temperature=0.0):
    """Initialize Gemini model with configurable temperature."""
    generation_config = {
        "temperature": temperature,
        "top_k": 1 if temperature == 0.0 else 40,
        "response_mime_type": "application/json",
    }
    
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    return genai.GenerativeModel(
        model_name='gemini-2.5-pro',
        generation_config=generation_config,
        safety_settings=safety_settings
    )


def generate_with_retry(model, prompt_parts) -> dict:
    """Helper to handle API calls and parsing."""
    response = model.generate_content(
        prompt_parts, 
        request_options={"timeout": 600}
    )
    
    if not response.parts:
        feedback = response.prompt_feedback
        raise ValueError(f"Gemini blocked the request. Reason: {feedback}")

    cleaned_text = response.text.strip()
    
    # Clean up markdown fences
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
    
    return json.loads(cleaned_text.strip())


def reconstruct_full_csv(ai_json, rubric_map):
    """
    Merges the AI's minimal output (ID, Score, Evidence) with the static rubric data.
    This ensures the Frontend gets the full text even though the AI didn't generate it.
    """
    ai_csv_text = ai_json.get('csv', '')
    if not ai_csv_text:
        logging.warning("AI return empty CSV string.")
        return ai_json 

    # 1. Parse the AI's minimal CSV
    ai_rows = []
    try:
        csv_file = io.StringIO(ai_csv_text)
        reader = csv.DictReader(csv_file)
        for row in reader:
             ai_rows.append(row)
    except Exception as e:
        logging.error(f"Failed to parse AI CSV output: {e}")
        return ai_json

    # 2. Prepare full output
    output_io = io.StringIO()
    # These headers must match what utils.py and the frontend expect
    headers = ['Question_Number', 'Status', 'Section', 'Question_Text', 'Maximum_Score', 'ai_score', 'evidence']
    writer = csv.DictWriter(output_io, fieldnames=headers)
    writer.writeheader()
    
    # 3. Join AI data with Rubric data
    for ai_row in ai_rows:
        # Clean keys (handle case sensitivity or whitespace from AI)
        clean_ai_row = {k.strip().lower(): v for k, v in ai_row.items() if k}
        
        # Find Question Number (handle variations like 'question_number', 'id', 'q_no')
        q_num = None
        for key in clean_ai_row:
            if 'question' in key or 'number' in key:
                q_num = clean_ai_row[key]
                break
        
        # Fallback: if not found by key, maybe it's the first value
        if not q_num and ai_row:
            q_num = list(ai_row.values())[0]

        q_num = str(q_num).strip()
        
        # Retrieve static data
        static_data = rubric_map.get(q_num)
        
        if not static_data:
            # If the AI hallucinated a question number not in our rubric, skip it
            continue

        # Find Score and Evidence in AI output
        ai_score_val = 'N/A'
        evidence_val = ''
        
        for k, v in clean_ai_row.items():
            if 'score' in k and 'max' not in k:
                ai_score_val = v
            if 'evidence' in k:
                evidence_val = v

        merged_row = {
            'Question_Number': q_num,
            'Status': static_data['Status'],
            'Section': static_data['Section'],
            'Question_Text': static_data['Question_Text'],
            'Maximum_Score': static_data['Maximum_Score'],
            'ai_score': ai_score_val,
            'evidence': evidence_val
        }
        writer.writerow(merged_row)
        
    # Replace the short CSV in the JSON with the full Reconstructed CSV
    ai_json['csv'] = output_io.getvalue()
    return ai_json


# ==============================================================================
# COMPATIBILITY FUNCTIONS FOR STREAMING SERVICE
# ==============================================================================

def process_pdf_for_gemini(pdf_path: str):
    """
    Process PDF for Gemini API.
    Returns tuple: (uploaded_file, paper_text, error)
    
    This is a compatibility function for gemini_service_streaming.py
    """
    try:
        # Try to upload PDF to Gemini
        uploaded_file = genai.upload_file(path=pdf_path, mime_type='application/pdf')
        return (uploaded_file, None, None)
    except Exception as e:
        logging.warning(f"PDF upload failed, falling back to text extraction: {e}")
        # Fall back to text extraction
        try:
            paper_text = extract_text_from_pdf(pdf_path)
            if not paper_text:
                return (None, None, "Could not extract text from PDF")
            return (None, paper_text, None)
        except Exception as extract_error:
            return (None, None, str(extract_error))


def get_gemini_response(prompt_text: str, uploaded_file=None, paper_text=None):
    """
    Get response from Gemini API.
    Returns the parsed JSON response.
    
    This is a compatibility function for gemini_service_streaming.py
    """
    model = get_model(temperature=0.0)
    
    if uploaded_file:
        prompt_payload = [prompt_text, uploaded_file]
    else:
        prompt_payload = [f"{prompt_text}\n\n--- PAPER TEXT ---\n{paper_text}"]
    
    return generate_with_retry(model, prompt_payload)


# ==============================================================================
# MAIN SCORING FUNCTION
# ==============================================================================

def score_paper_with_gemini(paper_file) -> dict:
    """Main scoring function for standard mode."""
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Save uploaded file
            temp_path = os.path.join(temp_dir, paper_file.filename)
            paper_file.save(temp_path)

            # Load Resources
            current_dir = pathlib.Path(__file__).parent.parent
            rubric_path = current_dir / "rubrics" / "cobidas_rubric.csv"
            
            with open(current_dir / "prompts" / "gemini_prompt.md", "r") as f:
                prompt_instructions = f.read()
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_content = f.read()
            
            # Load rubric map for post-processing
            rubric_map = load_rubric_map(rubric_path)
            if not rubric_map:
                raise ValueError("Rubric failed to load. Check CSV headers.")

            # Get model
            model = get_model(temperature=0.0)

            # --- OPTIMIZED PROMPT ---
            full_prompt_text = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT: Return the result strictly as JSON.
To save tokens, the 'csv' string must ONLY contain 3 columns: Question_Number, ai_score, evidence.
Do NOT repeat the Question Text or Section names.

Format:
{{
  "metadata": {{
    "title": "Paper Title",
    "authors": "Author Names",
    "year": "2024"
  }},
  "csv": "Question_Number,ai_score,evidence\\n1,2,\\"Quote...\\"\\n2,0.5,\\"Evidence...\\"
}}
"""

            logging.info(f"Attempt 1: Analyzing {paper_file.filename} via PDF Vision...")
            result = None
            try:
                uploaded_file = genai.upload_file(path=temp_path, mime_type='application/pdf')
                prompt_payload = [full_prompt_text, uploaded_file]
                result = generate_with_retry(model, prompt_payload)
            except ValueError as e:
                logging.warning(f"Attempt 1 failed. Switching to Text Fallback. Error: {e}")

            if not result:
                logging.info("Attempt 2: Analyzing extracted text...")
                raw_text = extract_text_from_pdf(temp_path)
                if not raw_text:
                    raise ValueError("Could not extract text from PDF.")
                
                prompt_payload = [f"{full_prompt_text}\n\n--- PAPER TEXT ---\n{raw_text}"]
                result = generate_with_retry(model, prompt_payload)

            # Reconstruct full CSV for the frontend
            final_result = reconstruct_full_csv(result, rubric_map)
            
            return final_result

        except Exception as e:
            logging.error(f"Scoring failed: {e}", exc_info=True)
            raise