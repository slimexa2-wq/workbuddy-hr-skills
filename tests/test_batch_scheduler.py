import unittest
import os
import shutil
import tempfile
import importlib.util
from typing import Dict

# Dynamic import due to hyphens in directory name
spec = importlib.util.spec_from_file_location(
    "batch_scheduler",
    "skills/supplier-commission-audit/scripts/batch_scheduler.py"
)
batch_scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch_scheduler)

class TestBatchScheduler(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.batch_dir = os.path.join(self.test_dir, 'batch')
        self.wage_dir = os.path.join(self.test_dir, 'wage')
        self.invoice_dir = os.path.join(self.test_dir, 'invoice')
        self.prev_dir = os.path.join(self.test_dir, 'prev')
        self.snapshot_dir = os.path.join(self.test_dir, 'snapshots')

        for d in [self.batch_dir, self.wage_dir, self.invoice_dir, self.prev_dir, self.snapshot_dir]:
            os.makedirs(d)

        # Create dummy files
        self.policy_file = os.path.join(self.test_dir, 'policy.sqlite')
        open(self.policy_file, 'w').close()

        # Project A
        open(os.path.join(self.batch_dir, '绵阳A项目结款.xlsx'), 'w').close()
        open(os.path.join(self.wage_dir, '2026年10月绵阳A项目工资.xlsx'), 'w').close()
        open(os.path.join(self.invoice_dir, '绵阳A项目考勤表.xlsx'), 'w').close()
        open(os.path.join(self.prev_dir, '绵阳A项目历史提成.xlsx'), 'w').close()

        # Project B (missing some)
        open(os.path.join(self.batch_dir, '成都B项目提成.xlsx'), 'w').close()
        open(os.path.join(self.wage_dir, '2026年10月成都B项目工资.xlsx'), 'w').close()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_auto_map_four_tables(self):
        mapping = batch_scheduler.auto_map_four_tables(
            self.batch_dir, self.wage_dir, self.invoice_dir, self.prev_dir, self.policy_file
        )

        self.assertIn('绵阳A项目', mapping)
        self.assertEqual(mapping['绵阳A项目']['wage_file'], os.path.join(self.wage_dir, '2026年10月绵阳A项目工资.xlsx'))
        self.assertEqual(mapping['绵阳A项目']['invoice_file'], os.path.join(self.invoice_dir, '绵阳A项目考勤表.xlsx'))
        self.assertEqual(mapping['绵阳A项目']['prev_batch_file'], os.path.join(self.prev_dir, '绵阳A项目历史提成.xlsx'))

        self.assertIn('成都B项目', mapping)
        self.assertEqual(mapping['成都B项目']['wage_file'], os.path.join(self.wage_dir, '2026年10月成都B项目工资.xlsx'))
        self.assertIsNone(mapping['成都B项目']['invoice_file'])
        self.assertIsNone(mapping['成都B项目']['prev_batch_file'])

    def test_parse_amount(self):
        self.assertEqual(batch_scheduler.parse_amount(100.5), 100.5)
        self.assertEqual(batch_scheduler.parse_amount("1,000.50"), 1000.5)
        self.assertEqual(batch_scheduler.parse_amount(None), 0.0)
        self.assertEqual(batch_scheduler.parse_amount(""), 0.0)
        self.assertEqual(batch_scheduler.parse_amount("dirty_string"), 0.0)

    def test_generate_supplier_summary(self):
        audit_results = [
            {'supplier': '供A', 'reported_amount': '1,000', 'passed_amount': 900, 'pending_amount': 100, 'overpaid_amount': 0},
            {'supplier': '供A', 'reported_amount': 500.5, 'passed_amount': 500.5, 'pending_amount': None, 'overpaid_amount': "dirty"},
            {'supplier': '供B', 'reported_amount': 2000, 'passed_amount': 1800, 'pending_amount': 0, 'overpaid_amount': 200}
        ]

        summary = batch_scheduler.generate_supplier_summary(audit_results)

        self.assertIn('供A', summary)
        self.assertEqual(summary['供A']['提报额'], 1500.5)
        self.assertEqual(summary['供A']['核实通过额'], 1400.5)
        self.assertEqual(summary['供A']['待核额'], 100.0)
        self.assertEqual(summary['供A']['多付差异'], 0.0)

        self.assertIn('供B', summary)
        self.assertEqual(summary['供B']['提报额'], 2000.0)
        self.assertEqual(summary['供B']['多付差异'], 200.0)

    def test_undo_snapshot(self):
        test_file = os.path.join(self.test_dir, 'test.xlsx')
        with open(test_file, 'w') as f:
            f.write("original")

        # Create snapshot
        snapshot_path = batch_scheduler.create_undo_snapshot(test_file, self.snapshot_dir)
        self.assertIsNotNone(snapshot_path)
        self.assertTrue(os.path.exists(snapshot_path))

        # Modify file
        with open(test_file, 'w') as f:
            f.write("modified")

        # Restore
        success = batch_scheduler.undo_last_action(test_file, self.snapshot_dir)
        self.assertTrue(success)

        # Verify restore
        with open(test_file, 'r') as f:
            content = f.read()
        self.assertEqual(content, "original")

if __name__ == '__main__':
    unittest.main()
