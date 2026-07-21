"""
gemini_service_high_accuracy.py

ULTRA HIGH-ACCURACY MODE
- 7 independent passes with varied temperatures (0.0, 0.05, 0.1, 0.15, 0.1, 0.05, 0.0)
- Gemini 3.1 Pro for maximum accuracy
- Strict majority voting (need 4/7 agreement)
- For any remaining ties, runs targeted tie-breakers until resolved

Philosophy: Cost doesn't matter, accuracy does.
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

# Reuse logic from main service
from .gemini_service import (
    load_rubric_map,
    reconstruct_full_csv,
    extract_text_from_pdf,
    client,
    SAFETY_SETTINGS,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# === CONFIGURATION ===
NUM_PASSES = 7
TEMPERATURES = [0.0, 0.05, 0.1, 0.15, 0.1, 0.05, 0.0]  # Symmetric, peaks at middle
MAJORITY_THRESHOLD = 4  # Need 4/7 to agree
MODEL_NAME = 'gemini-3.1-pro-preview'


def get_model(temperature: float):
    """Build the GenerateContentConfig for a request at the given temperature."""
    return types.GenerateContentConfig(
        temperature=temperature,
        top_k=40 if temperature > 0 else 1,
        response_mime_type="application/json",
        safety_settings=SAFETY_SETTINGS,
        http_options=types.HttpOptions(timeout=600_000),
    )


def generate_json_response(config, prompt_parts):
    """Executes a single model run and returns parsed JSON."""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt_parts,
            config=config,
        )
        if not response.candidates:
            raise ValueError(f"Empty response (Safety Block): {response.prompt_feedback}")

        cleaned = (response.text or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        logging.error(f"JSON parse failed: {e}")
        return None
    except Exception as e:
        logging.error(f"Generation failed: {e}")
        return None


def parse_ai_csv_to_dict(csv_text: str) -> dict:
    """
    Parses the 'Skinny CSV' from AI into a dictionary.
    Returns: { '1': {'ai_score': '2', 'evidence': '...'}, ... }
    """
    scores = {}
    if not csv_text:
        return scores

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            clean_row = {k.strip().lower(): v for k, v in row.items() if k}

            # Extract Question ID
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

                scores[q_id] = {
                    'ai_score': str(score).strip(),
                    'evidence': evidence
                }
    except Exception as e:
        logging.error(f"Error parsing CSV: {e}")

    return scores


def normalize_score(score: str) -> str:
    """Normalize score for comparison."""
    s = str(score).strip().upper()
    if s in ['N/A', 'NA', 'MISSING', '', 'NONE']:
        return 'N/A'
    try:
        f = float(s)
        # Round to 1 decimal to handle floating point issues
        f = round(f, 1)
        if f == int(f):
            return str(int(f))
        return str(f)
    except ValueError:
        return s


def get_majority_vote(votes: list) -> tuple:
    """
    Get majority vote from list of scores.
    Returns: (winning_score, vote_count, is_majority)
    """
    if not votes:
        return ('N/A', 0, False)
    
    # Filter out MISSING votes
    valid_votes = [v for v in votes if v != 'MISSING']
    if not valid_votes:
        return ('N/A', 0, False)
    
    counter = Counter(valid_votes)
    winner, count = counter.most_common(1)[0]
    is_majority = count >= MAJORITY_THRESHOLD
    
    return (winner, count, is_majority)


def score_paper_high_accuracy(paper_file) -> dict:
    """
    Ultra high-accuracy scoring with 7 passes and majority voting.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # === 1. SETUP ===
            temp_path = os.path.join(temp_dir, paper_file.filename)
            
            # Reset file pointer if it was consumed elsewhere
            try:
                paper_file.stream.seek(0)
            except (AttributeError, ValueError):
                # If seeking fails, the file might be closed or unseekable
                pass
            
            paper_file.save(temp_path)

            current_dir = pathlib.Path(__file__).parent.parent
            rubric_path = current_dir / "rubrics" / "cobidas_rubric.csv"

            with open(current_dir / "prompts" / "gemini_prompt.md", "r") as f:
                prompt_instructions = f.read()
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric_content = f.read()

            rubric_map = load_rubric_map(rubric_path)
            if not rubric_map:
                raise ValueError("Rubric failed to load.")

            logging.info(f"=== HIGH-ACCURACY MODE: {NUM_PASSES} passes with {MODEL_NAME} ===")

            # === 2. BUILD BASE PROMPT ===
            base_prompt = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

IMPORTANT: Return the result strictly as JSON.
The 'csv' string must ONLY contain 3 columns: Question_Number, ai_score, evidence.
Do NOT repeat the Question Text or Section names.

Format:
{{
  "metadata": {{
    "title": "Paper Title",
    "authors": "Author Names",
    "year": "2024"
  }},
  "csv": "Question_Number,ai_score,evidence\\n1,2,\\"Quote...\\"\\n2,0.5,\\"Evidence...\\""
}}
"""

            # === 3. UPLOAD FILE ONCE ===
            logging.info("Uploading PDF to Gemini...")
            uploaded_file = None
            paper_text = None

            try:
                uploaded_file = client.files.upload(file=temp_path, config=types.UploadFileConfig(mime_type='application/pdf'))
                logging.info("PDF uploaded successfully")
            except Exception as e:
                logging.warning(f"PDF upload failed ({e}), using text extraction")
                paper_text = extract_text_from_pdf(temp_path)
                if not paper_text:
                    raise ValueError("Could not extract text from PDF.")

            # === 4. RUN ALL PASSES ===
            all_scores = []  # List of dicts, one per pass
            metadata = {}

            for i in range(NUM_PASSES):
                temp = TEMPERATURES[i] if i < len(TEMPERATURES) else 0.1
                logging.info(f"Pass {i+1}/{NUM_PASSES} (temperature={temp})...")

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
                    logging.info(f"  Pass {i+1} complete: {len(scores)} questions scored")
                else:
                    logging.warning(f"  Pass {i+1} FAILED - will use other passes")
                    all_scores.append({})  # Empty dict for failed pass

            successful_passes = sum(1 for s in all_scores if s)
            logging.info(f"Completed {successful_passes}/{NUM_PASSES} successful passes")

            if successful_passes < 3:
                raise ValueError(f"Too many passes failed ({NUM_PASSES - successful_passes}/{NUM_PASSES}). Cannot establish consensus.")

            # === 5. INITIAL MAJORITY VOTE ===
            logging.info("Computing initial majority vote...")
            logging.info("=" * 60)
            
            final_scores = {}
            unresolved = []
            
            # Track vote distributions for logging
            unanimous_count = 0
            strong_majority_count = 0  # 6/7 or 5/7
            weak_majority_count = 0    # 4/7
            no_majority_count = 0

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
                
                # Detailed logging for each question
                vote_dist = Counter(votes)
                vote_str = ', '.join([f"{k}:{v}" for k, v in vote_dist.most_common()])

                if is_majority:
                    final_scores[q_id] = {
                        'ai_score': winner,
                        'evidence': evidences.get(winner, ''),
                        'confidence': f"{count}/{len(votes)}"
                    }
                    
                    # Categorize the strength of consensus
                    if count == len(votes):
                        unanimous_count += 1
                        logging.debug(f"  Q{q_id}: [{vote_str}] -> {winner} ({count}/{len(votes)}) ✓ UNANIMOUS")
                    elif count >= 5:
                        strong_majority_count += 1
                        logging.debug(f"  Q{q_id}: [{vote_str}] -> {winner} ({count}/{len(votes)}) ✓ STRONG")
                    else:
                        weak_majority_count += 1
                        logging.info(f"  Q{q_id}: [{vote_str}] -> {winner} ({count}/{len(votes)}) ✓ weak majority")
                else:
                    no_majority_count += 1
                    logging.warning(f"  Q{q_id}: [{vote_str}] -> NO MAJORITY (best: {winner} with {count}/{len(votes)}) ⚠️")
                    unresolved.append({
                        'q_id': q_id,
                        'votes': votes,
                        'evidences': evidences
                    })

            logging.info("=" * 60)
            logging.info(f"VOTE SUMMARY:")
            logging.info(f"  Unanimous (7/7):      {unanimous_count}")
            logging.info(f"  Strong (5-6/7):       {strong_majority_count}")
            logging.info(f"  Weak (4/7):           {weak_majority_count}")
            logging.info(f"  No majority (<4/7):   {no_majority_count}")
            logging.info(f"  TOTAL RESOLVED:       {len(final_scores)}/{len(rubric_map)}")
            logging.info(f"  NEEDS TIE-BREAKER:    {len(unresolved)}")
            logging.info("=" * 60)

            # === 6. TARGETED TIE-BREAKERS FOR UNRESOLVED ===
            if unresolved:
                logging.info(f"Running targeted tie-breakers for {len(unresolved)} questions...")
                logging.info(f"Unresolved questions: {[u['q_id'] for u in unresolved]}")
                
                unresolved_ids = [u['q_id'] for u in unresolved]
                
                # Run 3 more targeted passes at different temperatures
                tie_breaker_temps = [0.0, 0.1, 0.0]
                
                for tb_round, temp in enumerate(tie_breaker_temps):
                    if not unresolved_ids:
                        break
                        
                    logging.info(f"  Tie-breaker round {tb_round + 1}/3 (temp={temp}) for {len(unresolved_ids)} questions...")
                    
                    model = get_model(temp)
                    
                    # Build focused prompt
                    disputed_str = ', '.join(unresolved_ids)
                    tie_breaker_prompt = f"""{prompt_instructions}

--- START OF RUBRIC (cobidas_rubric.csv) ---
{rubric_content}
--- END OF RUBRIC ---

CRITICAL: Previous analyses disagreed on questions: {disputed_str}

Please CAREFULLY re-evaluate ONLY these specific questions: {disputed_str}
Take extra care to find evidence in the paper. If information is truly not present, score as 0 or N/A as appropriate.

Return JSON with ONLY these questions:
{{
  "metadata": {{}},
  "csv": "Question_Number,ai_score,evidence\\n..."
}}
"""
                    if uploaded_file:
                        prompt_content = [tie_breaker_prompt, uploaded_file]
                    else:
                        prompt_content = [f"{tie_breaker_prompt}\n\n--- PAPER TEXT ---\n{paper_text}"]

                    result = generate_json_response(model, prompt_content)
                    
                    if result:
                        tb_scores = parse_ai_csv_to_dict(result.get('csv', ''))
                        logging.info(f"    Tie-breaker returned {len(tb_scores)} scores")
                        
                        # Add these votes to unresolved items
                        for item in unresolved:
                            q_id = item['q_id']
                            if q_id in tb_scores:
                                score = normalize_score(tb_scores[q_id]['ai_score'])
                                item['votes'].append(score)
                                logging.info(f"    Q{q_id}: added vote '{score}' -> now {item['votes']}")
                                if score not in item['evidences']:
                                    item['evidences'][score] = tb_scores[q_id]['evidence']
                            else:
                                logging.warning(f"    Q{q_id}: NOT in tie-breaker response!")
                        
                        # Check if any are now resolved
                        still_unresolved = []
                        for item in unresolved:
                            winner, count, is_majority = get_majority_vote(item['votes'])
                            # Lower threshold for tie-breaker rounds (simple majority)
                            total_votes = len(item['votes'])
                            needed = total_votes // 2 + 1
                            
                            if count >= needed:
                                final_scores[item['q_id']] = {
                                    'ai_score': winner,
                                    'evidence': item['evidences'].get(winner, ''),
                                    'confidence': f"{count}/{total_votes} (resolved in tie-breaker)"
                                }
                                logging.info(f"    ✓ Q{item['q_id']} RESOLVED: {winner} ({count}/{total_votes})")
                            else:
                                still_unresolved.append(item)
                                logging.info(f"    ✗ Q{item['q_id']} still unresolved: best is {winner} ({count}/{total_votes}, need {needed})")
                        
                        resolved_this_round = len(unresolved) - len(still_unresolved)
                        logging.info(f"    Round {tb_round + 1} resolved {resolved_this_round} questions")
                        unresolved = still_unresolved
                        unresolved_ids = [u['q_id'] for u in unresolved]
                    else:
                        logging.error(f"    Tie-breaker round {tb_round + 1} FAILED")

            # === 7. FORCE RESOLVE ANY REMAINING ===
            if unresolved:
                logging.warning("=" * 60)
                logging.warning(f"FORCE-RESOLVING {len(unresolved)} questions with plurality vote...")
                for item in unresolved:
                    # Just take the most common vote, even if not majority
                    valid_votes = [v for v in item['votes'] if v != 'MISSING']
                    counter = Counter(valid_votes)
                    if counter:
                        winner, count = counter.most_common(1)[0]
                    else:
                        winner = 'N/A'
                        count = 0
                    
                    vote_dist = ', '.join([f"{k}:{v}" for k, v in counter.most_common()])
                    logging.warning(f"  Q{item['q_id']}: [{vote_dist}] -> FORCED to '{winner}' ({count}/{len(valid_votes)})")
                    
                    final_scores[item['q_id']] = {
                        'ai_score': winner,
                        'evidence': item['evidences'].get(winner, 'Consensus could not be reached.'),
                        'confidence': f"{count}/{len(item['votes'])} (forced)"
                    }
                logging.warning("=" * 60)

            # === 8. BUILD FINAL CSV ===
            logging.info("Building final consensus CSV...")
            final_csv = io.StringIO()
            writer = csv.DictWriter(final_csv, fieldnames=['Question_Number', 'ai_score', 'evidence'])
            writer.writeheader()

            for q_id in rubric_map.keys():
                data = final_scores.get(q_id, {'ai_score': 'N/A', 'evidence': 'Not scored.'})
                writer.writerow({
                    'Question_Number': q_id,
                    'ai_score': data['ai_score'],
                    'evidence': data['evidence']
                })

            # === 9. FINAL SCORE CALCULATION FOR LOGGING ===
            total_score = 0
            max_score = 0
            na_count = 0
            
            for q_id, data in final_scores.items():
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

            # === 10. RECONSTRUCT & RETURN ===
            final_result = {
                'metadata': metadata,
                'csv': final_csv.getvalue()
            }

            logging.info("=" * 60)
            logging.info(f"=== HIGH-ACCURACY COMPLETE ===")
            logging.info(f"  Model: {MODEL_NAME}")
            logging.info(f"  Main passes: {NUM_PASSES}")
            logging.info(f"  Successful passes: {successful_passes}")
            logging.info(f"  Tie-breaker rounds used: {3 - len([u for u in unresolved_ids]) if 'unresolved_ids' in dir() else 'N/A'}")
            logging.info(f"  Questions scored: {len(final_scores)}/{len(rubric_map)}")
            logging.info(f"  Questions marked N/A: {na_count}")
            logging.info(f"  FINAL SCORE: {total_score}/{max_score} = {percentage}%")
            logging.info("=" * 60)
            
            return reconstruct_full_csv(final_result, rubric_map)

        except Exception as e:
            logging.error(f"High-Accuracy scoring failed: {e}", exc_info=True)
            raise