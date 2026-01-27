import os
import pathlib
import logging
import tempfile
import json
import csv
import io
import re
from google import genai
from google.genai import types
from pypdf import PdfReader

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- 1. INITIALIZE CLIENT (New V2 SDK Way) ---
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not found.")
    
    # In V2, we create a client instance instead of using global config
    client = genai.Client(api_key=api_key)
    logging.info("Gemini V2 Client configured successfully.")
except Exception as e:
    logging.fatal(f"FATAL ERROR: Could not configure Gemini Client. {e}")

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
    """Loads the rubric CSV into a dictionary for fast lookup."""
    rubric_map = {}
    try:
        with open(rubric_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if 'Question_Number' not in reader.fieldnames:
                logging.error("Rubric CSV missing 'Question_Number' header.")
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
    return rubric_map

def generate_with_retry(model_id, contents, config) -> dict:
    """Helper to handle API calls and parsing with V2 SDK."""
    
    # V2 SDK call: client.models.generate_content
    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config=config
    )
    
    # Check if the response was blocked (V2 usually returns None or empty text)
    if not response.text:
        # In V2, safety/block reason is often in response.candidates[0].finish_reason
        raise ValueError(f"Gemini blocked the request or returned empty text.")

    cleaned_text = response.text.strip()
    
    # Clean up markdown fences
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
    
    return json.loads(cleaned_text.strip())

def reconstruct_full_csv(ai_json, rubric_map):
    """Merges AI output with static rubric data."""
    ai_csv_text = ai_json.get('csv', '')
    if not ai_csv_text: return ai_json 

    ai_rows = []
    try:
        csv_file = io.StringIO(ai_csv_text)
        reader = csv.DictReader(csv_file)
        for row in reader: ai_rows.append(row)
    except Exception: return ai_json

    output_io = io.StringIO()
    headers = ['Question_Number', 'Status', 'Section', 'Question_Text', 'Maximum_Score', 'ai_score', 'evidence']
    writer = csv.DictWriter(output_io, fieldnames=headers)
    writer.writeheader()
    
    for ai_row in ai_rows:
        # Clean keys
        clean_ai_row = {k.strip().lower(): v for k, v in ai_row.items() if k}
        
        # Find ID
        q_num = None
        for key in clean_ai_row:
            if 'question' in key or 'number' in key:
                q_num = clean_ai_row[key]
                break
        if not q_num and ai_row: q_num = list(ai_row.values())[0]
        q_num = str(q_num).strip()
        
        static_data = rubric_map.get(q_num)
        if not static_data: continue

        # Find Score/Evidence
        ai_score_val = 'N/A'
        evidence_val = ''
        for k, v in clean_ai_row.items():
            if 'score' in k and 'max' not in k: ai_score_val = v
            if 'evidence' in k: evidence_val = v

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

def score_paper_with_gemini(paper_file) -> dict:
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

            # --- 2. NEW CONFIG OBJECT (With Seed Support) ---
            conf = types.GenerateContentConfig(
                temperature=0.0,
                top_k=1,
                seed=42,  # <--- Now supported in V2!
                response_mime_type="application/json",
                safety_settings=[
                    types.SafetySetting(
                        category='HARM_CATEGORY_HARASSMENT',
                        threshold='BLOCK_NONE'
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_HATE_SPEECH',
                        threshold='BLOCK_NONE'
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
                        threshold='BLOCK_NONE'
                    ),
                    types.SafetySetting(
                        category='HARM_CATEGORY_DANGEROUS_CONTENT',
                        threshold='BLOCK_NONE'
                    )
                ]
            )

            prompt_text = f"""{prompt_instructions}

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
  "csv": "Question_Number,ai_score,evidence\\n1,2,\"Quote...\"\\n2,0.5,\"Evidence...\""
}}
"""

            logging.info(f"Attempt 1: Analyzing {paper_file.filename} via PDF Vision (V2 SDK)...")
            result = None
            try:
                # V2 SDK File Upload (handled differently, but client.models.generate_content supports paths directly!)
                # Note: For large PDFs, we still use the file API, but for simplicity here we assume standard upload
                # Actually, V2 handles local files gracefully if we read bytes.
                
                # To be safe with V2, we usually upload to File API first:
                uploaded_file = client.files.upload(path=temp_path)
                
                prompt_payload = [prompt_text, uploaded_file]
                result = generate_with_retry('gemini-2.5-pro', prompt_payload, conf) 
                # Note: 'gemini-2.5-pro' might not be in V2 public alias yet, fallback to 2.0-flash or check docs
                # If you have 2.5 access, ensure the model name is correct (e.g. 'gemini-2.5-pro-exp')
                
            except Exception as e:
                logging.warning(f"Attempt 1 failed. Switching to Text Fallback. Error: {e}")

            if not result:
                logging.info("Attempt 2: Analyzing extracted text...")
                raw_text = extract_text_from_pdf(temp_path)
                if not raw_text: raise ValueError("Could not extract text.")
                
                prompt_payload = [f"{prompt_text}\n\n--- PAPER TEXT ---\n{raw_text}"]
                # Retry with text
                result = generate_with_retry('gemini-2.0-flash', prompt_payload, conf)

            return reconstruct_full_csv(result, rubric_map)

        except Exception as e:
            logging.error(f"Scoring failed: {e}", exc_info=True)
            raise