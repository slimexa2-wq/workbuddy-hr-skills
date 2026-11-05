import unittest
import datetime
from ultra_modules.monthly_254_baseline_auditor_integration_bridge import audit

class TestMonthly254BaselineAuditor(unittest.TestCase):
    def setUp(self):
        self.current_date = datetime.date(2023, 10, 15)

    def test_normal_data(self):
        # 1. Normal standard data test
        records = [
            {"姓名": "Alice", "在职状态": "在职", "入职日期": "2023-10-01"},
            {"姓名": "Bob", "在职状态": "离职", "入职日期": "2023-10-01"},
            {"姓名": "Charlie", "在职状态": "在职", "入职日期": "2023-10-10"},
        ]
        result = audit(records, current_date=self.current_date)

        self.assertEqual(result["total_records_processed"], 3)
        self.assertEqual(result["active_count"], 2) # Alice, Charlie
        self.assertEqual(result["active_7_days_count"], 1) # Alice (14 days), Charlie (5 days)
        self.assertEqual(result["baseline"], 254)

    def test_dirty_data_self_healing(self):
        # 2. Dirty data self-healing: partial column names, missing status
        records = [
            # Partial match on "在职状态(最新)" -> maps to status
            {"员工姓名": "Dave", "在职状态(最新)": "Active", "入职时间": "2023/09/15"},
            # Missing status, but has join date -> heals to "在职"
            {"name": "Eve", "hire_date": "20230910"},
            # Unrelated dirty row
            {"something": "else", "age": 20},
            # Missing status, missing join_date -> heals to "未知" (inactive)
            {"emp_name": "Frank"}
        ]
        result = audit(records, current_date=self.current_date)

        self.assertEqual(result["total_records_processed"], 4)
        self.assertEqual(result["active_count"], 2) # Dave (Active), Eve (Healed)
        self.assertEqual(result["active_7_days_count"], 2) # Dave (30 days), Eve (35 days)

    def test_missing_parameters_fallback(self):
        # 3. Missing parameters default fallback (No arguments)
        result = audit()

        self.assertEqual(result["total_records_processed"], 0)
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["active_7_days_count"], 0)
        self.assertEqual(result["baseline"], 254)
        self.assertEqual(result["achievement_rate"], 0.0)
        self.assertFalse(result["is_baseline_met"])

        # 4. Invalid baseline type/value fallback
        result_invalid_baseline = audit(records=[], baseline=-10)
        self.assertEqual(result_invalid_baseline["baseline"], 254)

        result_invalid_baseline2 = audit(records=[], baseline="invalid")
        self.assertEqual(result_invalid_baseline2["baseline"], 254)

    def test_extreme_boundary_scenarios(self):
        # 5. Extreme boundary conditions: non-list input, nested dicts instead of list, extreme date formats
        records = {"emp_name": "Grace", "status": 1, "entry_date": "2023-10-08T10:20:30.123Z"} # single dict instead of list
        result = audit(records, current_date=self.current_date)

        self.assertEqual(result["total_records_processed"], 1)
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["active_7_days_count"], 1) # 2023-10-08 to 2023-10-15 is exactly 7 days

        # 6. Completely empty/garbage inputs
        garbage_input = [None, "string row", 123, []]
        result_garbage = audit(garbage_input)
        self.assertEqual(result_garbage["total_records_processed"], 0)
        self.assertEqual(result_garbage["active_count"], 0)

    def test_baseline_met_calculation(self):
        # 7. Test if baseline is met properly
        records = [{"status": "在职"} for _ in range(10)]
        result = audit(records, baseline=10)

        self.assertEqual(result["active_count"], 10)
        self.assertEqual(result["baseline"], 10)
        self.assertEqual(result["achievement_rate"], 1.0)
        self.assertTrue(result["is_baseline_met"])
        self.assertEqual(result["achievement_percentage"], "100.00%")

if __name__ == "__main__":
    unittest.main()
