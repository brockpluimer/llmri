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
    """Loads the rubric CSV into a dictionary for fast lookup."""
    rubric_map = {}
    try:
        with open(rubric_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # normalize keys just in case
                clean_row = {k.strip(): v.strip() for k, v in row.items()}
                if 'Question_Number' in clean_row:
                    rubric_map[clean_row['Question_Number']] = clean_row
    except Exception as e:
        logging.error(f"Failed to load rubric file: {e}")
    return rubric_map

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
    
    # Clean up markdown fences if present
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
    
    return json.loads(cleaned_text.strip())

def reconstruct_full_csv(ai_json, rubric_map):
    """
    Merges the AI's minimal output (ID, Score, Evidence) with the static rubric data
    (Question Text, Section, etc.) to create the full CSV format the frontend expects.
    """
    ai_csv_text = ai_json.get('csv', '')
    if not ai_csv_text:
        return ai_json 

    # Parse the AI's minimal CSV
    ai_rows = []
    try:
        csv_file = io.StringIO(ai_csv_text)
        reader = csv.DictReader(csv_file)
        for row in reader:
             ai_rows.append(row)
    except Exception:
        # If parsing fails, return as is (fallback)
        return ai_json

    # Prepare output
    output_io = io.StringIO()
    # The columns expected by utils.py and frontend
    headers = ['Question_Number', 'Status', 'Section', 'Question_Text', 'Maximum_Score', 'ai_score', 'evidence']
    writer = csv.DictWriter(output_io, fieldnames=headers)
    writer.writeheader()
    
    for ai_row in ai_rows:
        q_num = ai_row.get('Question_Number')
        if not q_num: continue
        
        # Look up static data from our loaded rubric
        static_data = rubric_map.get(q_num, {})
        
        merged_row = {
            'Question_Number': q_num,
            'Status': static_data.get('Status', 'Unknown'),
            'Section': static_data.get('Section', 'Unknown'),
            'Question_Text': static_data.get('Question_Text', 'Unknown'),
            'Maximum_Score': static_data.get('Maximum_Score', '0'),
            'ai_score': ai_row.get('ai_score', 'N/A'),
            'evidence': ai_row.get('evidence', '')
        }
        writer.writerow(merged_row)
        
    # Replace the short CSV in the JSON with the full Reconstructed CSV
    ai_json['csv'] = output_io.getvalue()
    return ai_json

def score_paper_with_gemini(paper_file) -> dict:
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

            # Config - Token Efficient Prompting
            generation_config = {
                "temperature": 0.0,
                "top_k": 1, 
                "response_mime_type": "application/json",
            }

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            model = genai.GenerativeModel(
                model_name='gemini-2.5-pro',
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # --- OPTIMIZED PROMPT ---
            # We explicitly ask for FEWER columns to save tokens and prevent truncation.
            full_prompt_text = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT: Return the result strictly as JSON.
To save space, the 'csv' string must ONLY contain 3 columns: Question_Number, ai_score, evidence.
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

            # --- ATTEMPT 1: PDF UPLOAD ---
            logging.info(f"Attempt 1: Analyzing {paper_file.filename} via PDF Vision...")
            result = None
            try:
                uploaded_file = genai.upload_file(path=temp_path, mime_type='application/pdf')
                prompt_payload = [full_prompt_text, uploaded_file]
                result = generate_with_retry(model, prompt_payload)
            except ValueError as e:
                logging.warning(f"Attempt 1 failed (Safety/Block). Switching to Text Fallback. Error: {e}")

            # --- ATTEMPT 2: TEXT FALLBACK ---
            if not result:
                logging.info("Attempt 2: Analyzing extracted text...")
                raw_text = extract_text_from_pdf(temp_path)
                if not raw_text:
                    raise ValueError("Could not extract text from PDF for fallback.")
                
                prompt_payload = [f"{full_prompt_text}\n\n--- PAPER TEXT ---\n{raw_text}"]
                result = generate_with_retry(model, prompt_payload)

            # --- POST-PROCESSING ---
            # Rehydrate the CSV with full details (Section, Question Text) so frontend works
            final_result = reconstruct_full_csv(result, rubric_map)
            
            return final_result

        except Exception as e:
            logging.error(f"Scoring failed: {e}", exc_info=True)
            raise