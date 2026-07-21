"""
gemini_service_high_accuracy_streaming.py

High-accuracy mode with real-time progress callbacks for SSE streaming.
"""

import os
import pathlib
import logging
import tempfile
import json
import csv
import io
from collections import Counter
from google.genai import types

from .gemini_service import (
    load_rubric_map,
    reconstruct_full_csv,
    extract_text_from_pdf,
    client,
    SAFETY_SETTINGS,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
NUM_PASSES = 7
TEMPERATURES = [0.0, 0.05, 0.1, 0.15, 0.1, 0.05, 0.0]
MAJORITY_THRESHOLD = 4
MODEL_NAME = 'gemini-3.1-pro-preview'


def get_model(temperature: float):
    return types.GenerateContentConfig(
        temperature=temperature,
        top_k=40 if temperature > 0 else 1,
        response_mime_type="application/json",
        safety_settings=SAFETY_SETTINGS,
        http_options=types.HttpOptions(timeout=600_000),
    )


def generate_json_response(config, prompt_parts):
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt_parts,
            config=config,
        )
        if not response.candidates:
            raise ValueError(f"Empty response: {response.prompt_feedback}")
        cleaned = (response.text or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())
    except Exception as e:
        logging.error(f"Generation failed: {e}")
        return None


def parse_ai_csv_to_dict(csv_text: str) -> dict:
    scores = {}
    if not csv_text:
        return scores
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            clean_row = {k.strip().lower(): v for k, v in row.items() if k}
            q_id = None
            for k in clean_row:
                if 'question' in k or 'number' in k:
                    q_id = clean_row[k]
                    break
            if not q_id and row:
                q_id = list(row.values())[0]
            if q_id:
                q_id = str(q_id).strip()
                score = 'N/A'
                evidence = ''
                for k, v in clean_row.items():
                    if 'score' in k and 'max' not in k:
                        score = v
                    if 'evidence' in k:
                        evidence = v
                scores[q_id] = {'ai_score': str(score).strip(), 'evidence': evidence}
    except Exception as e:
        logging.error(f"Error parsing CSV: {e}")
    return scores


def normalize_score(score: str) -> str:
    s = str(score).strip().upper()
    if s in ['N/A', 'NA', 'MISSING', '', 'NONE']:
        return 'N/A'
    try:
        f = float(s)
        f = round(f, 1)
        if f == int(f):
            return str(int(f))
        return str(f)
    except ValueError:
        return s


def get_majority_vote(votes: list) -> tuple:
    if not votes:
        return ('N/A', 0, False)
    valid_votes = [v for v in votes if v != 'MISSING']
    if not valid_votes:
        return ('N/A', 0, False)
    counter = Counter(valid_votes)
    winner, count = counter.most_common(1)[0]
    is_majority = count >= MAJORITY_THRESHOLD
    return (winner, count, is_majority)


def score_paper_high_accuracy_with_progress(file_path_or_file, progress_callback) -> dict:
    """
    High-accuracy scoring with progress callbacks.
    
    Args:
        file_path_or_file: Either a file path string or FileStorage object
        progress_callback: Function called with (event_type, data)
    
    progress_callback(event_type, data) is called throughout with:
    - 'upload': {'status': 'uploading'/'complete'}
    - 'pass_start': {'pass': 1, 'total': 7, 'temperature': 0.0}
    - 'pass_complete': {'pass': 1, 'total': 7, 'questions_scored': 82}
    - 'voting_start': {}
    - 'voting_result': {'unanimous': 61, 'strong': 12, 'weak': 8, 'unresolved': 1}
    - 'tiebreaker_start': {'questions': ['4', '30'], 'round': 1, 'total_rounds': 3}
    - 'tiebreaker_complete': {'round': 1, 'resolved': 0, 'remaining': 1}
    - 'force_resolve': {'questions': ['30']}
    - 'final_score': {'score': 75.0, 'raw': '63.0/84.0', 'na_count': 25}
    - 'log': {'message': '...', 'level': 'info'/'warning'/'error'}
    """
    
    def emit(event, data):
        if progress_callback:
            try:
                progress_callback(event, data)
            except Exception as e:
                logging.warning(f"Progress callback error: {e}")
    
    def log(message, level='info'):
        emit('log', {'message': message, 'level': level})
        getattr(logging, level)(message)

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Handle both file paths and file objects
            if isinstance(file_path_or_file, str):
                # It's already a file path - just use it
                temp_path = file_path_or_file
                filename = os.path.basename(file_path_or_file)
            else:
                # It's a file object - save it
                filename = file_path_or_file.filename
                temp_path = os.path.join(temp_dir, filename)
                
                # Reset file pointer if needed
                try:
                    file_path_or_file.stream.seek(0)
                except (AttributeError, ValueError):
                    pass
                
                file_path_or_file.save(temp_path)

            current_dir = pathlib.Path(__file__).parent.parent
            rubric_path = current_dir / "rubrics" / "cobidas_rubric.csv"

            with open(current_dir / "prompts" / "gemini_prompt.md", "r") as f:
                prompt_instructions = f.read()
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_content = f.read()

            rubric_map = load_rubric_map(rubric_path)
            if not rubric_map:
                raise ValueError("Rubric failed to load.")

            log(f"Starting HIGH-ACCURACY MODE: {NUM_PASSES} passes with {MODEL_NAME}")
            emit('init', {'passes': NUM_PASSES, 'model': MODEL_NAME, 'questions': len(rubric_map)})

            # Build prompt
            base_prompt = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT: Return the result strictly as JSON.
The 'csv' string must ONLY contain 3 columns: Question_Number, ai_score, evidence.

Format:
{{
  "metadata": {{"title": "...", "authors": "...", "year": "..."}},
  "csv": "Question_Number,ai_score,evidence\\n1,2,\\"Quote...\\""
}}
"""

            # Upload PDF
            emit('upload', {'status': 'uploading'})
            log("Uploading PDF to Gemini...")
            
            uploaded_file = None
            paper_text = None
            try:
                uploaded_file = client.files.upload(file=temp_path, config=types.UploadFileConfig(mime_type='application/pdf'))
                log("PDF uploaded successfully")
                emit('upload', {'status': 'complete', 'method': 'pdf'})
            except Exception as e:
                log(f"PDF upload failed, using text extraction: {e}", 'warning')
                paper_text = extract_text_from_pdf(temp_path)
                if not paper_text:
                    raise ValueError("Could not extract text from PDF.")
                emit('upload', {'status': 'complete', 'method': 'text'})

            # Run all passes
            all_scores = []
            metadata = {}

            for i in range(NUM_PASSES):
                temp = TEMPERATURES[i] if i < len(TEMPERATURES) else 0.1
                
                emit('pass_start', {'pass': i + 1, 'total': NUM_PASSES, 'temperature': temp})
                log(f"Pass {i+1}/{NUM_PASSES} (temperature={temp})...")

                model = get_model(temp)
                if uploaded_file:
                    prompt_content = [base_prompt, uploaded_file]
                else:
                    prompt_content = [f"{base_prompt}\n\n--- PAPER TEXT ---\n{paper_text}"]

                result = generate_json_response(model, prompt_content)

                if result:
                    if i == 0:
                        metadata = result.get('metadata', {})
                    scores = parse_ai_csv_to_dict(result.get('csv', ''))
                    all_scores.append(scores)
                    
                    emit('pass_complete', {'pass': i + 1, 'total': NUM_PASSES, 'questions_scored': len(scores)})
                    log(f"  Pass {i+1} complete: {len(scores)} questions scored")
                else:
                    log(f"  Pass {i+1} FAILED", 'warning')
                    all_scores.append({})
                    emit('pass_complete', {'pass': i + 1, 'total': NUM_PASSES, 'questions_scored': 0, 'failed': True})

            successful_passes = sum(1 for s in all_scores if s)
            log(f"Completed {successful_passes}/{NUM_PASSES} successful passes")

            if successful_passes < 3:
                raise ValueError(f"Too many passes failed ({NUM_PASSES - successful_passes}/{NUM_PASSES})")

            # Majority vote
            emit('voting_start', {})
            log("Computing majority vote...")

            final_scores = {}
            unresolved = []
            unanimous_count = 0
            strong_count = 0
            weak_count = 0

            for q_id in rubric_map.keys():
                votes = []
                evidences = {}
                for pass_scores in all_scores:
                    if pass_scores and q_id in pass_scores:
                        score = normalize_score(pass_scores[q_id]['ai_score'])
                        votes.append(score)
                        if score not in evidences:
                            evidences[score] = pass_scores[q_id]['evidence']

                winner, count, is_majority = get_majority_vote(votes)

                if is_majority:
                    final_scores[q_id] = {
                        'ai_score': winner,
                        'evidence': evidences.get(winner, ''),
                        'confidence': f"{count}/{len(votes)}"
                    }
                    if count == len(votes):
                        unanimous_count += 1
                    elif count >= 5:
                        strong_count += 1
                    else:
                        weak_count += 1
                else:
                    unresolved.append({'q_id': q_id, 'votes': votes, 'evidences': evidences})

            emit('voting_result', {
                'unanimous': unanimous_count,
                'strong': strong_count,
                'weak': weak_count,
                'unresolved': len(unresolved),
                'total': len(rubric_map)
            })
            
            log(f"Vote results: {unanimous_count} unanimous, {strong_count} strong, {weak_count} weak, {len(unresolved)} unresolved")

            # Tie-breakers
            if unresolved:
                unresolved_ids = [u['q_id'] for u in unresolved]
                emit('tiebreaker_start', {'questions': unresolved_ids, 'total_rounds': 3})
                log(f"Running tie-breakers for {len(unresolved)} questions: {unresolved_ids}")

                tie_breaker_temps = [0.0, 0.1, 0.0]

                for tb_round, temp in enumerate(tie_breaker_temps):
                    if not unresolved_ids:
                        break

                    emit('tiebreaker_round', {'round': tb_round + 1, 'total': 3, 'questions': len(unresolved_ids), 'temperature': temp})
                    log(f"  Tie-breaker round {tb_round + 1}/3 (temp={temp})...")

                    model = get_model(temp)
                    disputed_str = ', '.join(unresolved_ids)
                    
                    tb_prompt = f"""{prompt_instructions}

--- START OF RUBRIC ---
{rubric_content}
--- END OF RUBRIC ---

CRITICAL: Re-evaluate ONLY questions: {disputed_str}
Return JSON with ONLY these questions.
"""
                    if uploaded_file:
                        prompt_content = [tb_prompt, uploaded_file]
                    else:
                        prompt_content = [f"{tb_prompt}\n\n--- PAPER TEXT ---\n{paper_text}"]

                    result = generate_json_response(model, prompt_content)

                    if result:
                        tb_scores = parse_ai_csv_to_dict(result.get('csv', ''))
                        
                        for item in unresolved:
                            q_id = item['q_id']
                            if q_id in tb_scores:
                                score = normalize_score(tb_scores[q_id]['ai_score'])
                                item['votes'].append(score)
                                if score not in item['evidences']:
                                    item['evidences'][score] = tb_scores[q_id]['evidence']

                        # Check resolution
                        still_unresolved = []
                        for item in unresolved:
                            winner, count, _ = get_majority_vote(item['votes'])
                            needed = len(item['votes']) // 2 + 1
                            if count >= needed:
                                final_scores[item['q_id']] = {
                                    'ai_score': winner,
                                    'evidence': item['evidences'].get(winner, ''),
                                    'confidence': f"{count}/{len(item['votes'])} (tiebreaker)"
                                }
                            else:
                                still_unresolved.append(item)

                        resolved = len(unresolved) - len(still_unresolved)
                        emit('tiebreaker_complete', {'round': tb_round + 1, 'resolved': resolved, 'remaining': len(still_unresolved)})
                        log(f"    Round {tb_round + 1}: resolved {resolved}, remaining {len(still_unresolved)}")
                        
                        unresolved = still_unresolved
                        unresolved_ids = [u['q_id'] for u in unresolved]

            # Force resolve remaining
            if unresolved:
                force_ids = [u['q_id'] for u in unresolved]
                emit('force_resolve', {'questions': force_ids})
                log(f"Force-resolving {len(unresolved)} questions: {force_ids}", 'warning')

                for item in unresolved:
                    valid_votes = [v for v in item['votes'] if v != 'MISSING']
                    counter = Counter(valid_votes)
                    if counter:
                        winner, count = counter.most_common(1)[0]
                    else:
                        winner, count = 'N/A', 0

                    final_scores[item['q_id']] = {
                        'ai_score': winner,
                        'evidence': item['evidences'].get(winner, 'Consensus not reached.'),
                        'confidence': f"{count}/{len(item['votes'])} (forced)"
                    }

            # Build final CSV
            final_csv = io.StringIO()
            writer = csv.DictWriter(final_csv, fieldnames=['Question_Number', 'ai_score', 'evidence'])
            writer.writeheader()

            total_score = 0
            max_score = 0
            na_count = 0

            for q_id in rubric_map.keys():
                data = final_scores.get(q_id, {'ai_score': 'N/A', 'evidence': 'Not scored.'})
                writer.writerow({
                    'Question_Number': q_id,
                    'ai_score': data['ai_score'],
                    'evidence': data['evidence']
                })

                score_val = data['ai_score']
                max_val = rubric_map.get(q_id, {}).get('Maximum_Score', '0')

                if score_val == 'N/A':
                    na_count += 1
                else:
                    try:
                        total_score += float(score_val)
                        max_score += float(max_val)
                    except ValueError:
                        pass

            percentage = round((total_score / max_score * 100), 1) if max_score > 0 else 0

            emit('final_score', {
                'percentage': percentage,
                'raw_score': total_score,
                'max_score': max_score,
                'na_count': na_count,
                'questions_scored': len(final_scores)
            })
            
            log(f"FINAL SCORE: {total_score}/{max_score} = {percentage}%")

            return reconstruct_full_csv({'metadata': metadata, 'csv': final_csv.getvalue()}, rubric_map)

        except Exception as e:
            logging.error(f"High-Accuracy scoring failed: {e}", exc_info=True)
            emit('error', {'message': str(e)})
            raise