import csv
import io
import logging


def parse_gemini_csv_to_json(csv_string: str) -> list:
    """
    Convert a CSV formatted string into a list of dictionaries.
    
    Handles edge cases from Gemini output like None keys from malformed headers.
    
    Args:
        csv_string: A string containing data in CSV format from the AI.
        
    Returns:
        A list of sanitized dictionaries representing each rubric item.
        
    Raises:
        ValueError: If the input is empty or parsing fails.
    """
    if not csv_string:
        logging.error("CSV parsing failed: Input string is empty.")
        raise ValueError("Cannot parse an empty string.")

    sanitized_data = []
    
    try:
        csv_file = io.StringIO(csv_string)
        reader = csv.DictReader(csv_file)
        
        for row in reader:
            # Filter out None keys (caused by empty CSV columns)
            clean_row = {k: v for k, v in row.items() if k is not None}
            
            # Skip completely empty rows
            if not any(clean_row.values()):
                continue
                
            sanitized_data.append(clean_row)
        
        if not sanitized_data:
            logging.error("CSV parsing resulted in empty data. Check Gemini output format.")
            raise ValueError("CSV parsing resulted in no data.")

        logging.info(f"Successfully parsed CSV data: {len(sanitized_data)} items.")
        return sanitized_data
        
    except csv.Error as e:
        logging.error(f"Failed to parse CSV string: {e}\nInput string was:\n{csv_string[:500]}...")
        raise ValueError(f"CSV formatting error from model: {e}")


def extract_metadata_from_response(response_data: dict) -> dict:
    """
    Extract metadata from Gemini API response.
    
    This function is used by gemini_service_streaming.py to extract
    paper metadata (title, authors, year) from the API response.
    
    Args:
        response_data: Dictionary containing response data with optional 'metadata' key
        
    Returns:
        Dictionary with metadata fields (title, authors, year)
        Returns empty dict if no metadata found
        
    Example:
        Input: {"metadata": {"title": "fMRI Study", "authors": "Smith et al.", "year": "2024"}}
        Output: {"title": "fMRI Study", "authors": "Smith et al.", "year": "2024"}
    """
    if not response_data:
        return {}
    
    metadata = response_data.get('metadata', {})
    
    # Ensure we always return a dict with expected keys
    return {
        'title': metadata.get('title', ''),
        'authors': metadata.get('authors', ''),
        'year': metadata.get('year', '')
    }


def calculate_score_summary(results: list) -> dict:
    """
    Calculate summary statistics from scoring results.
    
    Args:
        results: List of dictionaries containing scoring data.
        
    Returns:
        Dictionary with total_score, max_score, percentage, and section breakdowns.
    """
    total_score = 0
    max_score = 0
    section_scores = {}
    
    for item in results:
        ai_score = item.get('ai_score', 'N/A')
        max_item_score = item.get('Maximum_Score', '0')
        section = item.get('Section', 'Unknown')
        
        # Initialize section if not seen
        if section not in section_scores:
            section_scores[section] = {'earned': 0, 'possible': 0, 'items': 0}
        
        section_scores[section]['items'] += 1
        
        # Skip N/A items for scoring
        if ai_score == 'N/A':
            continue
            
        try:
            score_val = float(ai_score)
            max_val = float(max_item_score)
            
            total_score += score_val
            max_score += max_val
            section_scores[section]['earned'] += score_val
            section_scores[section]['possible'] += max_val
            
        except (ValueError, TypeError):
            logging.warning(f"Could not parse score: {ai_score} / {max_item_score}")
            continue
    
    # Calculate percentages
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    
    for section in section_scores:
        possible = section_scores[section]['possible']
        earned = section_scores[section]['earned']
        section_scores[section]['percentage'] = (
            (earned / possible * 100) if possible > 0 else 0
        )
    
    return {
        'total_score': total_score,
        'max_score': max_score,
        'percentage': round(percentage, 1),
        'sections': section_scores
    }