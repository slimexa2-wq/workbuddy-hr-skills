import os
import concurrent.futures
from typing import List, Dict, Any, Union

class WpsLockConflictCleanerBatchPipeline:
    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    def is_lock_file(self, filename: str) -> bool:
        """Check if a filename matches macOS WPS/Excel lock file patterns."""
        return filename.startswith('.~lock.') or filename.startswith('~$')

    def process_path(self, path: str) -> Dict[str, Any]:
        """Process a single path to clean lock files."""
        result = {'path': path, 'deleted': [], 'errors': []}

        try:
            if not os.path.exists(path):
                return result

            if os.path.isfile(path):
                filename = os.path.basename(path)
                if self.is_lock_file(filename):
                    try:
                        os.remove(path)
                        result['deleted'].append(path)
                    except Exception as e:
                        result['errors'].append(f"{path}: {str(e)}")
            elif os.path.isdir(path):
                # Scan directory
                for root, _, files in os.walk(path):
                    for file in files:
                        if self.is_lock_file(file):
                            full_path = os.path.join(root, file)
                            try:
                                os.remove(full_path)
                                result['deleted'].append(full_path)
                            except Exception as e:
                                result['errors'].append(f"{full_path}: {str(e)}")
        except Exception as e:
            result['errors'].append(f"Error accessing path {path}: {str(e)}")

        return result

    def run(self, paths: Union[List[Any], Any] = None) -> Dict[str, Any]:
        """
        Run the cleaner on a batch of paths.
        Dirty data self-healing: handles None, non-list, non-string, etc.
        """
        # Self-healing: if no path provided, default to empty
        if paths is None:
            paths = []
        elif not isinstance(paths, list):
            paths = [paths]

        # Filter and clean dirty data
        clean_paths = []
        for p in paths:
            if isinstance(p, str) and p.strip():
                clean_paths.append(p.strip())

        snapshot = {
            'total_processed_paths': len(clean_paths),
            'total_deleted': 0,
            'deleted_files': [],
            'errors': []
        }

        if not clean_paths:
            return snapshot

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # High throughput concurrent processing
            future_to_path = {executor.submit(self.process_path, p): p for p in clean_paths}
            for future in concurrent.futures.as_completed(future_to_path):
                try:
                    res = future.result()
                    snapshot['deleted_files'].extend(res['deleted'])
                    snapshot['errors'].extend(res['errors'])
                except Exception as exc:
                    path = future_to_path[future]
                    snapshot['errors'].append(f"{path} generated an exception: {exc}")

        snapshot['total_deleted'] = len(snapshot['deleted_files'])
        return snapshot
