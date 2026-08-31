import re
from datetime import datetime
from typing import Tuple, Optional

def normalize_date(date_str: str) -> Tuple[Optional[str], str, float]:
    """
    Parses various date string formats and normalizes them to YYYY-MM-DD.
    Returns: (normalized_date, raw_date, confidence)
    """
    if not date_str:
        return None, "", 0.0

    raw = date_str.strip()
    cleaned = raw.replace(',', '').replace('.', '').strip()
    
    # 1. Look for YYYY-MM-DD or YYYY/MM/DD
    match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', cleaned)
    if match:
        y, m, d = match.groups()
        try:
            val = datetime(int(y), int(m), int(d)).date().isoformat()
            return val, raw, 1.0
        except ValueError:
            pass

    # 2. Look for DD/MM/YYYY or DD-MM-YYYY (Very common in Indian reports)
    match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', cleaned)
    if match:
        d, m, y = match.groups()
        
        # Ambiguous check: if both day and month are <= 12, there is ambiguity (e.g. 03/04/2026)
        # In India, it's almost always DD/MM/YYYY, but we flag it as 0.70 confidence instead of 1.0.
        is_ambiguous = int(d) <= 12 and int(m) <= 12
        conf = 0.70 if is_ambiguous else 0.95
        
        try:
            val = datetime(int(y), int(m), int(d)).date().isoformat()
            return val, raw, conf
        except ValueError:
            # Maybe it is MM/DD/YYYY (US style)
            try:
                val = datetime(int(y), int(d), int(m)).date().isoformat()
                return val, raw, 0.50
            except ValueError:
                pass

    # 3. Look for DD MMM YYYY or MMM DD YYYY (e.g. 12 Apr 2026, Apr 12 2026)
    months = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    # Match DD MMM YYYY (e.g. 12 Apr 2026, 12-Apr-2026)
    match = re.search(r'(\d{1,2})\s*[-]?\s*([a-zA-Z]{3,})\s*[-]?\s*(\d{4})', cleaned)
    if match:
        d, m_name, y = match.groups()
        m_lower = m_name.lower()
        if m_lower in months:
            m = months[m_lower]
            try:
                val = datetime(int(y), m, int(d)).date().isoformat()
                return val, raw, 1.0
            except ValueError:
                pass

    # Match MMM DD YYYY (e.g. Apr 12 2026, August 15 2026)
    match = re.search(r'([a-zA-Z]{3,})\s+(\d{1,2})\s+(\d{4})', cleaned)
    if match:
        m_name, d, y = match.groups()
        m_lower = m_name.lower()
        if m_lower in months:
            m = months[m_lower]
            try:
                val = datetime(int(y), m, int(d)).date().isoformat()
                return val, raw, 1.0
            except ValueError:
                pass

    return None, raw, 0.0
