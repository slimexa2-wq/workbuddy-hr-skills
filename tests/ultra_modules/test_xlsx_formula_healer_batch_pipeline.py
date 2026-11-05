import unittest
import time
from ultra_modules.xlsx_formula_healer_batch_pipeline import XlsxFormulaHealerBatchPipeline

class TestXlsxFormulaHealerBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = XlsxFormulaHealerBatchPipeline(max_workers=5)

    def test_normal_records(self):
        records = [
            {"id": 1, "name": "Alice", "score": 95},
            {"id": 2, "name": "Bob", "score": 88}
        ]
        task_id = self.pipeline.submit_batch(records)
        self.assertIsInstance(task_id, str)

        # Wait for completion
        while True:
            progress = self.pipeline.get_progress(task_id)
            if progress and progress['status'] == 'completed':
                break
            time.sleep(0.1)

        result = self.pipeline.get_result(task_id)
        self.assertIsNotNone(result)
        self.assertEqual(len(result['result']), 2)

        healed_records = [r['healed'] for r in result['result']]
        self.assertEqual(healed_records[0]['score'], 95)
        self.assertEqual(healed_records[1]['name'], "Bob")

    def test_dirty_data_self_healing(self):
        records = [
            {"id": 1, "value1": "#DIV/0!", "value2": "#REF!", "value3": "#value!", "value4": "Circular reference detected"},
            {"id": 2, "text_num1": "  123  ", "text_num2": "45.67", "valid_text": "hello"}
        ]
        task_id = self.pipeline.submit_batch(records)

        # Wait for completion
        while True:
            progress = self.pipeline.get_progress(task_id)
            if progress and progress['status'] == 'completed':
                break
            time.sleep(0.1)

        result = self.pipeline.get_result(task_id)
        self.assertIsNotNone(result)

        healed_records = [r['healed'] for r in result['result']]

        # Check healing for row 1
        self.assertEqual(healed_records[0]['value1'], 0)
        self.assertEqual(healed_records[0]['value2'], "REFERENCE_ERROR")
        self.assertEqual(healed_records[0]['value3'], "VALUE_ERROR")
        self.assertEqual(healed_records[0]['value4'], "CIRCULAR_REFERENCE_ERROR")

        # Check healing for row 2
        self.assertEqual(healed_records[1]['text_num1'], 123)
        self.assertEqual(healed_records[1]['text_num2'], 45.67)
        self.assertEqual(healed_records[1]['valid_text'], "hello")

    def test_missing_parameter_fallback(self):
        # Test None submission
        task_id = self.pipeline.submit_batch(None)

        while True:
            progress = self.pipeline.get_progress(task_id)
            if progress and progress['status'] == 'completed':
                break
            time.sleep(0.1)

        result = self.pipeline.get_result(task_id)
        self.assertIsNotNone(result)
        self.assertEqual(len(result['result']), 0)

        # Test malformed record
        records = [
            None,
            "not a dict",
            {}
        ]
        task_id2 = self.pipeline.submit_batch(records)

        while True:
            progress = self.pipeline.get_progress(task_id2)
            if progress and progress['status'] == 'completed':
                break
            time.sleep(0.1)

        result2 = self.pipeline.get_result(task_id2)
        self.assertEqual(len(result2['result']), 3)
        self.assertEqual(result2['result'][0]['status'], 'error')
        self.assertEqual(result2['result'][1]['status'], 'error')
        self.assertEqual(result2['result'][2]['status'], 'success')
        self.assertEqual(result2['result'][2]['healed'], {})

    def test_extreme_edge_cases(self):
        # Submit 1000 records
        records = [{"id": i, "val": "#REF!"} for i in range(1000)]
        task_id = self.pipeline.submit_batch(records)

        while True:
            progress = self.pipeline.get_progress(task_id)
            if progress and progress['status'] == 'completed':
                break
            time.sleep(0.1)

        result = self.pipeline.get_result(task_id)
        self.assertIsNotNone(result)
        self.assertEqual(len(result['result']), 1000)

        healed_records = [r['healed'] for r in result['result']]
        self.assertEqual(healed_records[0]['val'], "REFERENCE_ERROR")
        self.assertEqual(healed_records[999]['val'], "REFERENCE_ERROR")

    def test_progress_snapshot(self):
        records = [{"id": i, "val": i} for i in range(500)]
        task_id = self.pipeline.submit_batch(records)

        # Immediate check (zero-blocking)
        progress = self.pipeline.get_progress(task_id)
        self.assertIsNotNone(progress)
        self.assertIn(progress['status'], ['processing', 'completed'])
        self.assertIn('progress', progress)
        self.assertEqual(progress['total'], 500)

        while True:
            progress = self.pipeline.get_progress(task_id)
            if progress and progress['status'] == 'completed':
                break
            time.sleep(0.1)

        final_progress = self.pipeline.get_progress(task_id)
        self.assertEqual(final_progress['progress'], 1.0)
        self.assertEqual(final_progress['processed'], 500)
        self.assertEqual(final_progress['status'], 'completed')

if __name__ == '__main__':
    unittest.main()
