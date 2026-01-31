# backend/scorer/analytics.py
"""
Simple analytics tracking for LLMRI.
Tracks paper processing counts by day/mode.
In-memory storage (resets on server restart).
For persistent storage, use Redis or a database.
"""

import time
from datetime import datetime, timedelta
from collections import defaultdict
import threading

# Thread-safe lock for analytics updates
_lock = threading.Lock()

# Storage structure:
# {
#   '2026-01-28': {'standard': 5, 'high-accuracy': 2},
#   '2026-01-27': {'standard': 3, 'high-accuracy': 1},
# }
_daily_stats = defaultdict(lambda: defaultdict(int))

# Track individual requests for more detail
# [{'timestamp': ..., 'mode': ..., 'ip_hash': ..., 'success': ...}, ...]
_request_log = []

# Maximum request log size (to prevent memory issues)
MAX_REQUEST_LOG = 10000


def _get_today():
    """Get today's date string."""
    return datetime.utcnow().strftime('%Y-%m-%d')


def _hash_ip(ip: str) -> str:
    """Hash IP for privacy (just keep first two octets)."""
    parts = ip.split('.')
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}.x.x"
    return "unknown"


def track_analysis(mode: str, client_ip: str, success: bool = True):
    """
    Track a paper analysis.
    
    Args:
        mode: 'standard' or 'high-accuracy'
        client_ip: Client IP address (will be hashed)
        success: Whether the analysis completed successfully
    """
    with _lock:
        today = _get_today()
        _daily_stats[today][mode] += 1
        
        # Add to request log
        _request_log.append({
            'timestamp': datetime.utcnow().isoformat(),
            'date': today,
            'mode': mode,
            'ip_hash': _hash_ip(client_ip),
            'success': success
        })
        
        # Trim log if too large
        if len(_request_log) > MAX_REQUEST_LOG:
            _request_log.pop(0)


def get_stats():
    """
    Get analytics statistics.
    
    Returns:
        dict with today, week, month, all-time stats
    """
    with _lock:
        now = datetime.utcnow()
        today = now.strftime('%Y-%m-%d')
        
        # Calculate date ranges
        week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        month_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Aggregate stats
        stats = {
            'today': {'standard': 0, 'high-accuracy': 0, 'total': 0},
            'week': {'standard': 0, 'high-accuracy': 0, 'total': 0},
            'month': {'standard': 0, 'high-accuracy': 0, 'total': 0},
            'all_time': {'standard': 0, 'high-accuracy': 0, 'total': 0},
            'daily_breakdown': {},
            'generated_at': now.isoformat()
        }
        
        for date_str, modes in _daily_stats.items():
            day_total = sum(modes.values())
            standard = modes.get('standard', 0)
            high_accuracy = modes.get('high-accuracy', 0)
            
            # All time
            stats['all_time']['standard'] += standard
            stats['all_time']['high-accuracy'] += high_accuracy
            stats['all_time']['total'] += day_total
            
            # Today
            if date_str == today:
                stats['today']['standard'] = standard
                stats['today']['high-accuracy'] = high_accuracy
                stats['today']['total'] = day_total
            
            # This week
            if date_str >= week_ago:
                stats['week']['standard'] += standard
                stats['week']['high-accuracy'] += high_accuracy
                stats['week']['total'] += day_total
            
            # This month
            if date_str >= month_ago:
                stats['month']['standard'] += standard
                stats['month']['high-accuracy'] += high_accuracy
                stats['month']['total'] += day_total
            
            # Daily breakdown (last 30 days)
            if date_str >= month_ago:
                stats['daily_breakdown'][date_str] = {
                    'standard': standard,
                    'high-accuracy': high_accuracy,
                    'total': day_total
                }
        
        # Sort daily breakdown by date
        stats['daily_breakdown'] = dict(sorted(stats['daily_breakdown'].items()))
        
        # Unique users (approximate, based on hashed IPs)
        unique_ips_today = set()
        unique_ips_week = set()
        unique_ips_month = set()
        unique_ips_all = set()
        
        for req in _request_log:
            unique_ips_all.add(req['ip_hash'])
            if req['date'] == today:
                unique_ips_today.add(req['ip_hash'])
            if req['date'] >= week_ago:
                unique_ips_week.add(req['ip_hash'])
            if req['date'] >= month_ago:
                unique_ips_month.add(req['ip_hash'])
        
        stats['unique_users'] = {
            'today': len(unique_ips_today),
            'week': len(unique_ips_week),
            'month': len(unique_ips_month),
            'all_time': len(unique_ips_all)
        }
        
        return stats


def get_recent_requests(limit: int = 50):
    """Get the most recent requests (for debugging)."""
    with _lock:
        return list(reversed(_request_log[-limit:]))