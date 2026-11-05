import re
from typing import List, Dict, Any, Optional

def identify_orphan_processes_to_reap(
    process_list: Optional[List[Dict[Any, Any]]] = None,
    target_keywords: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Identifies orphan processes (PPID=1) matching specific keywords for reaping.

    Args:
        process_list: List of process dictionaries. Expected keys: 'pid', 'ppid', 'cmd' or 'command'.
        target_keywords: List of keywords to match in the command. Defaults to ['agent', 'playwright', 'mcp'].

    Returns:
        List of cleaned process dictionaries that are orphans and match the keywords.
    """
    # 0-config default fallback
    if process_list is None:
        process_list = []

    if target_keywords is None:
        target_keywords = ['agent', 'playwright', 'mcp']

    if not isinstance(process_list, list):
        # dirty data fallback
        return []

    reap_list = []

    # Pre-compile regex for efficiency and case-preserving check (re.IGNORECASE)
    # Using re.escape for safety on keywords
    keyword_patterns = [re.compile(re.escape(str(kw)), re.IGNORECASE) for kw in target_keywords if kw]

    for proc in process_list:
        if not isinstance(proc, dict):
            continue

        # Silent dirty data cleaning
        raw_pid = proc.get('pid')
        raw_ppid = proc.get('ppid')

        try:
            pid = int(raw_pid) if raw_pid is not None else -1
        except (ValueError, TypeError):
            pid = -1

        try:
            ppid = int(raw_ppid) if raw_ppid is not None else -1
        except (ValueError, TypeError):
            ppid = -1

        cmd = str(proc.get('cmd') or proc.get('command') or '')

        # Check if orphan (PPID = 1)
        if ppid == 1 and pid > 0:
            # Check keywords
            for pattern in keyword_patterns:
                if pattern.search(cmd):
                    reap_list.append({
                        'pid': pid,
                        'ppid': ppid,
                        'cmd': cmd
                    })
                    break

    return reap_list
