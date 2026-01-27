"""
gemini_service_high_accuracy.py

High-accuracy mode: Runs analysis multiple times and uses majority vote
to resolve disagreements. More expensive but more consistent results.
"""

import os
import pathlib
import logging
import tempfile
import json
import csv
import io
from collections import Counter
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
    """Fallback: Extract text if Gemini blocks PDF."""
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
    """Load rubric CSV into dictionary for reconstruction."""
    rubric_map = {}
    try:
        with open(rubric_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
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


def get_model():
    """Initialize Gemini model with strict settings."""
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
    
    return genai.GenerativeModel(
        model_name='gemini-2.5-pro',
        generation_config=generation_config,
        safety_settings=safety_settings
    )


def parse_ai_response(response_text: str) -> dict:
    """Parse JSON response from Gemini."""
    cleaned = response_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def parse_csv_to_dict(csv_text: str) -> dict:
    """Convert CSV string to dict keyed by Question_Number."""
    results = {}
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            q_num = None
            clean_row = {k.strip().lower(): v for k, v in row.items() if k}
            
            for key in clean_row:
                if 'question' in key or 'number' in key:
                    q_num = clean_row[key]
                    break
            
            if not q_num and row:
                q_num = list(row.values())[0]
            
            if q_num:
                q_num = str(q_num).strip()
                score = 'N/A'
                evidence = ''
                
                for k, v in clean_row.items():
                    if 'score' in k and 'max' not in k:
                        score = v
                    if 'evidence' in k:
                        evidence = v
                
                results[q_num] = {'ai_score': score, 'evidence': evidence}
    except Exception as e:
        logging.error(f"Failed to parse CSV: {e}")
    return results


def run_single_analysis(model, prompt_text, uploaded_file=None, paper_text=None) -> dict:
    """Run a single analysis pass."""
    if uploaded_file:
        prompt_payload = [prompt_text, uploaded_file]
    else:
        prompt_payload = [f"{prompt_text}\n\n--- PAPER TEXT ---\n{paper_text}"]
    
    response = model.generate_content(
        prompt_payload,
        request_options={"timeout": 600}
    )
    
    if not response.parts:
        raise ValueError(f"Gemini blocked request: {response.prompt_feedback}")
    
    return parse_ai_response(response.text)


def run_targeted_analysis(model, prompt_text, questions: list, uploaded_file=None, paper_text=None) -> dict:
    """Run analysis on specific questions only."""
    targeted_prompt = f"""{prompt_text}

IMPORTANT: Only score these specific questions: {', '.join(questions)}
Skip all other questions in the rubric.
"""
    
    if uploaded_file:
        prompt_payload = [targeted_prompt, uploaded_file]
    else:
        prompt_payload = [f"{targeted_prompt}\n\n--- PAPER TEXT ---\n{paper_text}"]
    
    response = model.generate_content(
        prompt_payload,
        request_options={"timeout": 600}
    )
    
    if not response.parts:
        raise ValueError(f"Gemini blocked request: {response.prompt_feedback}")
    
    return parse_ai_response(response.text)


def find_disagreements(results_list: list) -> list:
    """Find question numbers where results disagree."""
    if not results_list:
        return []
    
    all_questions = set()
    for r in results_list:
        all_questions.update(r.keys())
    
    disagreements = []
    for q in all_questions:
        scores = [r.get(q, {}).get('ai_score', 'MISSING') for r in results_list]
        # Normalize scores for comparison
        normalized = [str(s).strip().upper() for s in scores]
        if len(set(normalized)) > 1:
            disagreements.append(q)
    
    return disagreements


def get_majority_vote(results_list: list, question: str) -> dict:
    """Get majority vote for a specific question."""
    scores = []
    evidences = {}
    
    for r in results_list:
        if question in r:
            score = str(r[question].get('ai_score', 'N/A')).strip()
            scores.append(score)
            evidences[score] = r[question].get('evidence', '')
    
    if not scores:
        return {'ai_score': 'N/A', 'evidence': 'No consensus reached.'}
    
    # Find most common score
    counter = Counter(scores)
    winner, count = counter.most_common(1)[0]
    
    return {'ai_score': winner, 'evidence': evidences.get(winner, '')}


def merge_results_with_majority(all_runs: list, rubric_map: dict) -> dict:
    """Merge all runs using majority vote for each question."""
    final_scores = {}
    
    all_questions = set()
    for run in all_runs:
        all_questions.update(run.keys())
    
    for q in all_questions:
        final_scores[q] = get_majority_vote(all_runs, q)
    
    return final_scores


def reconstruct_full_csv(final_scores: dict, rubric_map: dict, metadata: dict) -> dict:
    """Reconstruct full CSV from final scores."""
    output_io = io.StringIO()
    headers = ['Question_Number', 'Status', 'Section', 'Question_Text', 'Maximum_Score', 'ai_score', 'evidence']
    writer = csv.DictWriter(output_io, fieldnames=headers)
    writer.writeheader()
    
    for q_num, static_data in rubric_map.items():
        score_data = final_scores.get(q_num, {'ai_score': 'N/A', 'evidence': 'Not scored.'})
        
        merged_row = {
            'Question_Number': q_num,
            'Status': static_data['Status'],
            'Section': static_data['Section'],
            'Question_Text': static_data['Question_Text'],
            'Maximum_Score': static_data['Maximum_Score'],
            'ai_score': score_data['ai_score'],
            'evidence': score_data['evidence']
        }
        writer.writerow(merged_row)
    
    return {
        'metadata': metadata,
        'csv': output_io.getvalue()
    }


def score_paper_high_accuracy(paper_file) -> dict:
    """
    High-accuracy scoring with majority vote.
    
    Strategy:
    1. Run twice
    2. If disagreements, run 3rd time on disputed questions
    3. Continue until majority (3/5) or max 5 runs
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Save uploaded file
            temp_path = os.path.join(temp_dir, paper_file.filename)
            paper_file.save(temp_path)
            
            # Load resources
            current_dir = pathlib.Path(__file__).parent.parent
            rubric_path = current_dir / "rubrics" / "cobidas_rubric.csv"
            
            with open(current_dir / "prompts" / "gemini_prompt.md", "r") as f:
                prompt_instructions = f.read()
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_content = f.read()
            
            rubric_map = load_rubric_map(rubric_path)
            if not rubric_map:
                raise ValueError("Rubric failed to load.")
            
            model = get_model()
            
            # Build prompt
            full_prompt = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT: Return the result strictly as JSON.
The 'csv' string must ONLY contain 3 columns: Question_Number, ai_score, evidence.

Format:
{{
  "metadata": {{
    "title": "Paper Title",
    "authors": "Author Names",
    "year": "2024"
  }},
  "csv": "Question_Number,ai_score,evidence\\n1,2,\\"Quote...\\"\\n2,0,\\"Information not found.\\""
}}
"""
            
            # Try PDF upload first
            uploaded_file = None
            paper_text = None
            
            try:
                logging.info("Uploading PDF to Gemini...")
                uploaded_file = genai.upload_file(path=temp_path, mime_type='application/pdf')
            except Exception as e:
                logging.warning(f"PDF upload failed, using text extraction: {e}")
                paper_text = extract_text_from_pdf(temp_path)
                if not paper_text:
                    raise ValueError("Could not extract text from PDF.")
            
            # === MAJORITY VOTE LOGIC ===
            all_runs = []
            metadata = {}
            
            # Run 1
            logging.info("High-accuracy mode: Run 1/5...")
            result1 = run_single_analysis(model, full_prompt, uploaded_file, paper_text)
            metadata = result1.get('metadata', {})
            run1_scores = parse_csv_to_dict(result1.get('csv', ''))
            all_runs.append(run1_scores)
            
            # Run 2
            logging.info("High-accuracy mode: Run 2/5...")
            result2 = run_single_analysis(model, full_prompt, uploaded_file, paper_text)
            run2_scores = parse_csv_to_dict(result2.get('csv', ''))
            all_runs.append(run2_scores)
            
            # Check for disagreements
            disagreements = find_disagreements(all_runs)
            logging.info(f"Disagreements after 2 runs: {len(disagreements)} questions")
            
            # Runs 3-5: Only if needed, only on disputed questions
            run_num = 3
            while disagreements and run_num <= 5:
                logging.info(f"High-accuracy mode: Run {run_num}/5 on {len(disagreements)} disputed questions...")
                
                try:
                    result_n = run_targeted_analysis(
                        model, full_prompt, disagreements, uploaded_file, paper_text
                    )
                    run_n_scores = parse_csv_to_dict(result_n.get('csv', ''))
                    
                    # Merge targeted results into a full dict (other questions unchanged)
                    full_run = {}
                    for q in rubric_map.keys():
                        if q in run_n_scores:
                            full_run[q] = run_n_scores[q]
                        elif all_runs:
                            # Use previous consensus for non-disputed
                            full_run[q] = get_majority_vote(all_runs, q)
                    
                    all_runs.append(full_run)
                    
                except Exception as e:
                    logging.warning(f"Run {run_num} failed: {e}")
                
                # Recalculate disagreements
                disagreements = find_disagreements(all_runs)
                logging.info(f"Remaining disagreements: {len(disagreements)}")
                
                run_num += 1
            
            # Final merge with majority vote
            logging.info(f"Finalizing results from {len(all_runs)} runs...")
            final_scores = merge_results_with_majority(all_runs, rubric_map)
            
            return reconstruct_full_csv(final_scores, rubric_map, metadata)
            
        except Exception as e:
            logging.error(f"High-accuracy scoring failed: {e}", exc_info=True)
            raise