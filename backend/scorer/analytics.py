# backend/scorer/analytics.py
"""
Analytics tracking for LLMRI using Supabase.
Tracks paper processing counts with persistent storage.
"""

import os
import logging
import hashlib
from datetime import datetime, timedelta

# Try to import supabase, fall back to in-memory if not available
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logging.warning("Supabase not installed. Using in-memory analytics.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = None

def init_supabase():
    """Initialize Supabase client."""
    global supabase
    if not SUPABASE_AVAILABLE:
        return False
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_KEY not set. Using in-memory analytics.")
        return False
    
    try:
        supabase = create_client(url, key)
        logger.info("Supabase analytics initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {e}")
        return False

# Initialize on module load
init_supabase()


def _hash_ip(ip: str) -> str:
    """Hash IP for privacy (keep first two octets visible)."""
    if not ip:
        return "unknown"
    parts = ip.split('.')
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}.x.x"
    return "unknown"


def _hash_filename(filename: str) -> str:
    """Create a hash of filename for tracking unique papers."""
    if not filename:
        return None
    return hashlib.md5(filename.encode()).hexdigest()[:16]


def track_analysis(mode: str, client_ip: str, success: bool = True, 
                   processing_time: float = None, filename: str = None):
    """
    Track a paper analysis in Supabase.
    
    Args:
        mode: 'standard' or 'high-accuracy'
        client_ip: Client IP address (will be hashed)
        success: Whether the analysis completed successfully
        processing_time: Time taken in seconds
        filename: Original filename (will be hashed)
    """
    if not supabase:
        logger.debug("Supabase not available, skipping analytics")
        return
    
    try:
        data = {
            "mode": mode,
            "ip_hash": _hash_ip(client_ip),
            "success": success,
            "processing_time_seconds": processing_time,
            "filename_hash": _hash_filename(filename) if filename else None
        }
        
        result = supabase.table("llmri_analytics").insert(data).execute()
        logger.debug(f"Analytics tracked: {mode}, success={success}")
        
    except Exception as e:
        logger.error(f"Failed to track analytics: {e}")


def get_stats() -> dict:
    """
    Get analytics statistics from Supabase.
    
    Returns:
        dict with today, week, month, all-time stats
    """
    if not supabase:
        return {"error": "Supabase not configured"}
    
    try:
        now = datetime.utcnow()
        today = now.strftime('%Y-%m-%d')
        week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        month_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Get all records from last 30 days for detailed breakdown
        result = supabase.table("llmri_analytics")\
            .select("*")\
            .gte("date", month_ago)\
            .execute()
        
        records = result.data if result.data else []
        
        # Get all-time totals
        all_time_result = supabase.table("llmri_analytics")\
            .select("mode, success", count="exact")\
            .execute()
        
        all_records = all_time_result.data if all_time_result.data else []
        
        # Initialize stats
        stats = {
            'today': {'standard': 0, 'high-accuracy': 0, 'total': 0, 'success': 0, 'failed': 0},
            'week': {'standard': 0, 'high-accuracy': 0, 'total': 0, 'success': 0, 'failed': 0},
            'month': {'standard': 0, 'high-accuracy': 0, 'total': 0, 'success': 0, 'failed': 0},
            'all_time': {'standard': 0, 'high-accuracy': 0, 'total': 0, 'success': 0, 'failed': 0},
            'daily_breakdown': {},
            'unique_users': {'today': set(), 'week': set(), 'month': set()},
            'avg_processing_time': {'standard': [], 'high-accuracy': []},
            'generated_at': now.isoformat()
        }
        
        # Process monthly records
        for record in records:
            record_date = record.get('date', '')
            mode = record.get('mode', 'standard')
            success = record.get('success', True)
            ip_hash = record.get('ip_hash', '')
            proc_time = record.get('processing_time_seconds')
            
            # Daily breakdown
            if record_date not in stats['daily_breakdown']:
                stats['daily_breakdown'][record_date] = {
                    'standard': 0, 'high-accuracy': 0, 'total': 0
                }
            stats['daily_breakdown'][record_date][mode] = \
                stats['daily_breakdown'][record_date].get(mode, 0) + 1
            stats['daily_breakdown'][record_date]['total'] += 1
            
            # Month stats
            stats['month'][mode] += 1
            stats['month']['total'] += 1
            if success:
                stats['month']['success'] += 1
            else:
                stats['month']['failed'] += 1
            stats['unique_users']['month'].add(ip_hash)
            
            # Week stats
            if record_date >= week_ago:
                stats['week'][mode] += 1
                stats['week']['total'] += 1
                if success:
                    stats['week']['success'] += 1
                else:
                    stats['week']['failed'] += 1
                stats['unique_users']['week'].add(ip_hash)
            
            # Today stats
            if record_date == today:
                stats['today'][mode] += 1
                stats['today']['total'] += 1
                if success:
                    stats['today']['success'] += 1
                else:
                    stats['today']['failed'] += 1
                stats['unique_users']['today'].add(ip_hash)
            
            # Processing time
            if proc_time and success:
                stats['avg_processing_time'][mode].append(proc_time)
        
        # Process all-time records
        for record in all_records:
            mode = record.get('mode', 'standard')
            success = record.get('success', True)
            stats['all_time'][mode] += 1
            stats['all_time']['total'] += 1
            if success:
                stats['all_time']['success'] += 1
            else:
                stats['all_time']['failed'] += 1
        
        # Convert sets to counts
        stats['unique_users'] = {
            'today': len(stats['unique_users']['today']),
            'week': len(stats['unique_users']['week']),
            'month': len(stats['unique_users']['month'])
        }
        
        # Calculate average processing times
        for mode in ['standard', 'high-accuracy']:
            times = stats['avg_processing_time'][mode]
            if times:
                stats['avg_processing_time'][mode] = round(sum(times) / len(times), 1)
            else:
                stats['avg_processing_time'][mode] = None
        
        # Sort daily breakdown
        stats['daily_breakdown'] = dict(sorted(stats['daily_breakdown'].items()))
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"error": str(e)}


def get_recent_requests(limit: int = 50) -> list:
    """Get the most recent requests."""
    if not supabase:
        return []
    
    try:
        result = supabase.table("llmri_analytics")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        logger.error(f"Failed to get recent requests: {e}")
        return []