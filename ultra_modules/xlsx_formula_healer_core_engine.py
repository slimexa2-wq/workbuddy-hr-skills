class XlsxFormulaHealerCoreEngine:
    def __init__(self, fallback_value=0, strict_mode=False):
        self.fallback_value = fallback_value if fallback_value is not None else 0
        self.strict_mode = strict_mode if strict_mode is not None else False
        self.error_types = ["#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!"]

    def heal_error_values(self, data):
        """
        Heals error values in a matrix (list of lists) or a flat list.
        Replaces known Excel error strings with the fallback_value.
        """
        if not data:
            return []

        if isinstance(data, list):
            if all(isinstance(row, list) for row in data):
                return [[self.fallback_value if cell in self.error_types else cell for cell in row] for row in data]
            else:
                return [self.fallback_value if cell in self.error_types else cell for cell in data]
        return data

    def heal_text_as_number(self, data):
        """
        Scans data and converts string representations of numbers into actual floats or ints.
        """
        if not data:
            return []

        def convert(val):
            if isinstance(val, str):
                stripped = val.strip()
                try:
                    if '.' in stripped:
                        return float(stripped)
                    return int(stripped)
                except ValueError:
                    return val
            return val

        if isinstance(data, list):
            if all(isinstance(row, list) for row in data):
                return [[convert(cell) for cell in row] for row in data]
            else:
                return [convert(cell) for cell in data]
        return data

    def detect_circular_dependencies(self, dependencies):
        """
        Detects circular dependencies in a graph represented as an adjacency list.
        Uses Tarjan's Strongly Connected Components algorithm.
        Returns a list of strongly connected components (lists of nodes) that form a cycle.
        If dependencies is None, returns an empty list.
        """
        if not dependencies:
            return []

        index_counter = [0]
        stack = []
        lowlink = {}
        index = {}
        result = []

        def strongconnect(node):
            index[node] = index_counter[0]
            lowlink[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)

            successors = dependencies.get(node, [])
            for successor in successors:
                if successor not in index:
                    strongconnect(successor)
                    lowlink[node] = min(lowlink[node], lowlink[successor])
                elif successor in stack:
                    lowlink[node] = min(lowlink[node], index[successor])

            if lowlink[node] == index[node]:
                connected_component = []
                while True:
                    successor = stack.pop()
                    connected_component.append(successor)
                    if successor == node:
                        break

                # A component is a cycle if it has more than 1 node
                # or if it has 1 node that has an edge to itself.
                if len(connected_component) > 1 or node in dependencies.get(node, []):
                    result.append(connected_component)

        for node in dependencies:
            if node not in index:
                strongconnect(node)

        return result
