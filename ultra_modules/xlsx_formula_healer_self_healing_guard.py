import time
import copy

class XlsxFormulaHealerSelfHealingGuard:
    """
    Excel report healer for #REF!/#DIV/0!/#VALUE!/circular dependencies/text numbers.
    Features silent self-healing (no popups) and a 5-second one-click undo snapshot.
    """

    ERROR_TYPES = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!"}

    def __init__(self, fallback_value=0, undo_window_seconds=5.0):
        self.fallback_value = fallback_value if fallback_value is not None else 0
        self.undo_window_seconds = undo_window_seconds if undo_window_seconds is not None else 5.0
        self._snapshot_data = None
        self._snapshot_dependencies = None
        self._snapshot_timestamp = 0.0

    def heal(self, data, dependencies=None):
        """
        Main entry point for healing. Saves a snapshot for 5 seconds, then silently repairs data and dependencies.
        Returns a tuple of (healed_data, healed_dependencies).
        """
        # Save snapshot using deepcopy
        self._snapshot_data = copy.deepcopy(data) if data is not None else None
        self._snapshot_dependencies = copy.deepcopy(dependencies) if dependencies is not None else None
        self._snapshot_timestamp = time.time()

        # Heal data
        healed_data = self._heal_data(data)

        # Heal dependencies
        healed_dependencies = self._heal_dependencies(dependencies)

        return healed_data, healed_dependencies

    def _heal_data(self, data):
        """
        Recursively traverses and sanitizes nested data structures (lists, dicts, strings).
        Replaces error strings and converts text-as-numbers to floats/ints.
        """
        if data is None:
            return None

        if isinstance(data, list):
            return [self._heal_data(item) for item in data]

        if isinstance(data, dict):
            return {self._heal_data(k): self._heal_data(v) for k, v in data.items()}

        if isinstance(data, str):
            stripped = data.strip()
            if stripped in self.ERROR_TYPES:
                return self.fallback_value

            # Try to convert text-as-number
            try:
                if '.' in stripped:
                    return float(stripped)
                return int(stripped)
            except ValueError:
                return data

        return data

    def _heal_dependencies(self, dependencies):
        """
        Uses DFS to detect and silently remove cycle-inducing edges.
        Expects dependencies as a dictionary representing an adjacency list (node -> list of nodes).
        Returns a new adjacency list with cycles broken.
        """
        if not dependencies:
            return {} if not isinstance(dependencies, dict) else dependencies

        # Default fallback: ensure it's a dict
        if not isinstance(dependencies, dict):
            return {}

        healed_deps = {}
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)

            healed_edges = []

            # Use original dependencies list or empty list if node not present
            edges = dependencies.get(node, [])
            if edges is None:
                edges = []
            elif not isinstance(edges, list):
                edges = [edges]

            for neighbor in edges:
                if neighbor not in visited:
                    if dfs(neighbor):
                        # Not a cycle, keep edge
                        healed_edges.append(neighbor)
                elif neighbor not in rec_stack:
                    # Visited but not in current recursion stack, keep edge (cross/forward edge)
                    healed_edges.append(neighbor)
                # Else: Cycle detected! Silently ignore (break) the edge by not appending to healed_edges

            healed_deps[node] = healed_edges
            rec_stack.remove(node)
            return True

        for node in dependencies:
            if node not in visited:
                dfs(node)

        # Clean up any implicitly added nodes that were not in original dependencies dict
        final_deps = {k: v for k, v in healed_deps.items() if k in dependencies}

        # The loop checking for missing nodes is redundant because dfs will visit
        # all nodes and healed_deps already contains them (since we iterate over
        # all nodes in dependencies).
        return final_deps

    def undo(self):
        """
        Returns the snapshot (data, dependencies) if called within the undo window,
        restoring the original state.
        Returns (None, None) if expired or no snapshot exists.
        """
        if self._snapshot_timestamp == 0.0:
            return None, None

        current_time = time.time()
        if current_time - self._snapshot_timestamp <= self.undo_window_seconds:
            # Consume the snapshot
            snap_data = self._snapshot_data
            snap_deps = self._snapshot_dependencies

            # Clear snapshot
            self._snapshot_data = None
            self._snapshot_dependencies = None
            self._snapshot_timestamp = 0.0

            return snap_data, snap_deps

        return None, None
