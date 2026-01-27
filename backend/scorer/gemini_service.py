# backend/scorer/gemini_service.py

import os
import pathlib
import logging
import tempfile
import json
import csv
import io
import google.genai as genai  # UPDATED to the new library
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

# ==============================================================================
# HELPER FUNCTIONS (Preserving all original logic)
# ==============================================================================

def load_rubric_map(rubric_path):
    """Loads the rubric CSV into a dictionary for fast lookup."""
    rubric_map = {}
    try:
        with open(rubric_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if 'Question_Number' not in reader.fieldnames:
                logging.error(f"Rubric CSV is missing 'Question_Number'. Found: {reader.fieldnames}")
                return {}
            for row in reader:
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

def reconstruct_full_csv(ai_json, rubric_map):
    """Merges the AI's minimal output with the static rubric data."""
    ai_csv_text = ai_json.get('csv', '')
    if not ai_csv_text:
        logging.warning("AI returned empty CSV string.")
        return ai_json 

    ai_rows = []
    try:
        reader = csv.DictReader(io.StringIO(ai_csv_text))
        for row in reader:
             ai_rows.append(row)
    except Exception as e:
        logging.error(f"Failed to parse AI CSV output: {e}")
        return ai_json

    output_io = io.StringIO()
    headers = ['Question_Number', 'Status', 'Section', 'Question_Text', 'Maximum_Score', 'ai_score', 'evidence']
    writer = csv.DictWriter(output_io, fieldnames=headers)
    writer.writeheader()
    
    for ai_row in ai_rows:
        clean_ai_row = {k.strip().lower(): v for k, v in ai_row.items() if k}
        
        q_num = None
        for key in clean_ai_row:
            if 'question' in key or 'number' in key:
                q_num = clean_ai_row[key]
                break
        if not q_num and ai_row:
            q_num = list(ai_row.values())[0]
        q_num = str(q_num).strip()
        
        static_data = rubric_map.get(q_num)
        if not static_data:
            continue

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
        
    ai_json['csv'] = output_io.getvalue()
    return ai_json

# ==============================================================================
# NEW REUSABLE FUNCTIONS (Required by streaming services)
# ==============================================================================

def process_pdf_for_gemini(paper_file):
    """
    Reads a PDF, extracts text, and prepares the complete prompt for Gemini.
    This function is now self-contained and reusable.
    """
    try:
        paper_file.seek(0)
        reader = PdfReader(paper_file)
        paper_text = "".join(page.extract_text() or "" for page in reader.pages)

        if not paper_text.strip():
            logging.warning("PDF text extraction resulted in empty content.")
            return None, None
            
        current_dir = pathlib.Path(__file__).parent.parent
        with open(current_dir / "prompts" / "gemini_prompt.md", "r") as f:
            base_prompt = f.read()

        # NOTE: This creates a simple prompt suitable for standard text-based analysis.
        # The more advanced logic in `score_paper_with_gemini` builds its own prompt.
        combined_prompt = f"{base_prompt}\n\n---\n\n{paper_text}"
        
        return paper_text, {'combined_prompt': combined_prompt}

    except Exception as e:
        logging.error(f"Failed to process PDF for simple mode: {e}")
        return None, None

def get_gemini_response(prompt_text):
    """
    A reusable, text-only Gemini call for the standard mode.
    Uses a faster model and returns the raw CSV text.
    """
    try:
        # Using a faster, more cost-effective model for the standard mode
        model = genai.GenerativeModel('gemini-1.5-flash')
        logging.info("Sending request to Gemini 1.5 Flash for standard analysis...")
        response = model.generate_content(prompt_text, request_options={"timeout": 600})
        return response.text
    except Exception as e:
        logging.error(f"Standard Gemini call failed: {e}", exc_info=True)
        return None

# ==============================================================================
# ORIGINAL MAIN FUNCTION (Unchanged, for high-accuracy and non-streaming)
# ==============================================================================

def score_paper_with_gemini(paper_file) -> dict:
    """
    The original, high-accuracy function. Uses PDF Vision with a text fallback
    and reconstructs the final CSV.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            temp_path = os.path.join(temp_dir, paper_file.filename)
            paper_file.save(temp_path)

            current_dir = pathlib.Path(__file__).parent.parent
            rubric_path = current_dir / "rubrics" / "cobidas_rubric.csv"
            
            with open(current_dir / "prompts" / "gemini_prompt.md", "r") as f:
                prompt_instructions = f.read()
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_content = f.read()
            
            rubric_map = load_rubric_map(rubric_path)
            if not rubric_map:
                raise ValueError("Rubric failed to load. Check CSV headers.")

            generation_config = {"temperature": 0.0, "top_k": 1, "response_mime_type": "application/json"}
            safety_settings = {category: HarmBlockThreshold.BLOCK_NONE for category in HarmCategory}

            model = genai.GenerativeModel(
                model_name='gemini-1.5-pro', # Use high-accuracy model
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            full_prompt_text = f"""{prompt_instructions}\n\n--- START OF RUBRIC (cobidas_rubric.csv) ---\n{rubric_content}\n--- END OF RUBRIC ---\n\nIMPORTANT: Return the result strictly as JSON. To save tokens, the 'csv' string must ONLY contain 3 columns: Question_Number, ai_score, evidence.\n\nFormat:\n{{\n  "metadata": {{ "title": "...", "authors": "...", "year": "..." }},\n  "csv": "Question_Number,ai_score,evidence\\n1,2,\\"Quote...\\"\\n2,0.5,\\"Evidence...\\""\n}}"""

            logging.info(f"Attempt 1: Analyzing {paper_file.filename} via PDF Vision...")
            result_json = None
            try:
                uploaded_file = genai.upload_file(path=temp_path, mime_type='application/pdf')
                response = model.generate_content([full_prompt_text, uploaded_file], request_options={"timeout": 600})
                cleaned_text = response.text.strip().strip("```json").strip("```").strip()
                result_json = json.loads(cleaned_text)
            except Exception as e:
                logging.warning(f"Attempt 1 (PDF Vision) failed. Switching to Text Fallback. Error: {e}")

            if not result_json:
                logging.info("Attempt 2: Analyzing extracted text...")
                reader = PdfReader(temp_path)
                raw_text = "".join(page.extract_text() or "" for page in reader.pages)
                if not raw_text:
                    raise ValueError("Could not extract text from PDF for fallback.")
                
                response = model.generate_content([f"{full_prompt_text}\n\n--- PAPER TEXT ---\n{raw_text}"], request_options={"timeout": 600})
                cleaned_text = response.text.strip().strip("```json").strip("```").strip()
                result_json = json.loads(cleaned_text)

            return reconstruct_full_csv(result_json, rubric_map)

        except Exception as e:
            logging.error(f"High-accuracy scoring failed: {e}", exc_info=True)
            raise