import time
import random
import datetime

class SyntheticFixtureGenerator:
    """
    Generates synthetic fixtures for Monday 3-Reports.
    Includes edge cases such as missing values, garbled text, and huge strings.
    """
    def __init__(self, data_size=10):
        self.data_size = data_size

    def generate_project_requirements(self):
        """Generates mock data for project requirements report."""
        data = []
        for i in range(self.data_size):
            req = {
                "project_id": f"PRJ-{i:04d}",
                "name": f"Project {i}" if random.random() > 0.1 else None,  # Inject nulls
                "status": random.choice(["Open", "Closed", "Pending", "???😱龘"]),  # Inject garbled text
                "description": "A" * (1000 if i % 10 == 0 else 10)  # Inject huge strings for stress testing
            }
            data.append(req)
        return data

    def generate_student_workers(self):
        """Generates mock data for student workers report."""
        data = []
        for i in range(self.data_size):
            worker = {
                "worker_id": f"SW-{i:04d}",
                "name": f"Student {i}" if random.random() > 0.05 else "", # Empty string
                "department": random.choice(["Engineering", "HR", "Sales", None]),
                "join_date": self._generate_random_date()
            }
            data.append(worker)
        return data

    def generate_campus_recruitment(self):
        """Generates mock data for campus recruitment performance."""
        data = []
        for i in range(self.data_size):
            recruitment = {
                "candidate_id": f"CR-{i:04d}",
                "university": f"University {i % 5}",
                "offer_status": random.choice(["Accepted", "Declined", None, "InvalidStatus!@#"]),
                "offer_date": self._generate_random_date(cross_year=True)
            }
            data.append(recruitment)
        return data

    def _generate_random_date(self, cross_year=False):
        """Generates dates, specifically testing cross-month and cross-year boundaries."""
        if cross_year and random.random() > 0.5:
            # Simulate cross-year boundary (Dec 31 to Jan 1)
            return random.choice(["2023-12-31", "2024-01-01"])

        # Cross month boundary
        return random.choice(["2023-11-30", "2023-12-01"])

    def generate_all_fixtures(self):
        return {
            "project_requirements": self.generate_project_requirements(),
            "student_workers": self.generate_student_workers(),
            "campus_recruitment": self.generate_campus_recruitment()
        }


class BenchmarkRunner:
    """
    Engine to synthesize reports and run benchmarks.
    Demonstrates self-healing, defaults for missing params, and high performance.
    """
    def __init__(self, fixtures=None):
        # Default to a safe minimal setup if no parameters are passed
        self.fixtures = fixtures or SyntheticFixtureGenerator(data_size=100).generate_all_fixtures()

    def _heal_data(self, record, key, default_val):
        """Silent dirty data repair."""
        if key not in record or record[key] is None or record[key] == "":
            record[key] = default_val
        return record

    def synthesize_project_requirements(self):
        start_time = time.time()
        processed = []
        for record in self.fixtures.get("project_requirements", []):
            record = self._heal_data(record, "name", "Unnamed Project")
            record = self._heal_data(record, "status", "Unknown")
            # Truncate description to simulate fast processing of huge strings
            record["description"] = record.get("description", "")[:50]
            processed.append(record)

        duration = time.time() - start_time
        return {"processed_count": len(processed), "duration_sec": duration}

    def synthesize_student_workers(self):
        start_time = time.time()
        processed = []
        for record in self.fixtures.get("student_workers", []):
            record = self._heal_data(record, "name", "Unknown Student")
            record = self._heal_data(record, "department", "Unassigned")
            processed.append(record)

        duration = time.time() - start_time
        return {"processed_count": len(processed), "duration_sec": duration}

    def synthesize_campus_recruitment(self):
        start_time = time.time()
        processed = []
        for record in self.fixtures.get("campus_recruitment", []):
            record = self._heal_data(record, "offer_status", "Pending")
            # Standardize date if garbled or malformed
            try:
                datetime.datetime.strptime(record.get("offer_date", ""), "%Y-%m-%d")
            except ValueError:
                record["offer_date"] = "1970-01-01" # Default fallback for bad dates
            processed.append(record)

        duration = time.time() - start_time
        return {"processed_count": len(processed), "duration_sec": duration}

    def run_all(self):
        """
        One-click entry point. Zero config required.
        Ensures execution is < 3 seconds total.
        """
        results = {}

        results["project_requirements"] = self.synthesize_project_requirements()
        results["student_workers"] = self.synthesize_student_workers()
        results["campus_recruitment"] = self.synthesize_campus_recruitment()

        total_duration = sum(res["duration_sec"] for res in results.values())
        results["total_duration_sec"] = total_duration
        results["status"] = "SUCCESS" if total_duration < 3.0 else "FAILED_TIMEOUT"

        return results

if __name__ == "__main__":
    print("Running Monday 3-Reports Benchmark Suite (1-click execution)...")
    runner = BenchmarkRunner()
    results = runner.run_all()
    print(results)
