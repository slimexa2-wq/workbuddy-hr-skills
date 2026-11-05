import unittest
import os
import tempfile
import shutil
from PIL import Image

from ultra_modules.dossier_image_upright_batch_pipeline import process_dossier_batch, process_single_record

class TestDossierImageUprightBatchPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.output_dir, exist_ok=True)

        # Create a valid test image
        self.valid_image_path = os.path.join(self.test_dir, 'valid.jpg')
        img = Image.new('RGB', (100, 100), color='red')
        img.save(self.valid_image_path)

        # Create an invalid test image (e.g. text file pretending to be image)
        self.invalid_image_path = os.path.join(self.test_dir, 'invalid.jpg')
        with open(self.invalid_image_path, 'w') as f:
            f.write("This is not an image.")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_valid_image_processing(self):
        records = [{'id': '1', 'image_path': self.valid_image_path}]
        result = process_dossier_batch(records, self.output_dir)

        self.assertEqual(result['total'], 1)
        self.assertEqual(result['success'], 1)
        self.assertEqual(result['failed'], 0)
        self.assertTrue(os.path.exists(result['results'][0]['output_path']))
        self.assertTrue(result['results'][0]['output_path'].endswith('.docx'))

    def test_dirty_data_healing_invalid_image(self):
        # The pipeline should gracefully handle an invalid image file without crashing
        records = [{'id': '2', 'image_path': self.invalid_image_path}]
        result = process_dossier_batch(records, self.output_dir)

        self.assertEqual(result['total'], 1)
        self.assertEqual(result['success'], 0)
        self.assertEqual(result['failed'], 1)
        self.assertIsNotNone(result['results'][0]['error'])

    def test_missing_params_default_fallback(self):
        # Missing image_path or id
        records = [
            {'image_path': self.valid_image_path}, # Missing id
            {'id': '3'}, # Missing image_path
            {} # Missing both
        ]
        result = process_dossier_batch(records, self.output_dir)

        self.assertEqual(result['total'], 3)
        self.assertEqual(result['failed'], 2)
        self.assertEqual(result['success'], 1) # The one with valid image_path but missing ID should succeed with default ID 'unknown'

        # Check the successful one
        success_record = next(r for r in result['results'] if r['status'] == 'success')
        self.assertEqual(success_record['id'], 'unknown')
        self.assertTrue(os.path.exists(success_record['output_path']))

    def test_boundary_conditions_empty_batch(self):
        # Empty batch should be handled gracefully
        result = process_dossier_batch([], self.output_dir)

        self.assertEqual(result['total'], 0)
        self.assertEqual(result['success'], 0)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len(result['results']), 0)

    def test_concurrent_batch_processing_large(self):
        # Simulate processing 20 records
        records = [{'id': str(i), 'image_path': self.valid_image_path} for i in range(20)]
        result = process_dossier_batch(records, self.output_dir, max_workers=5)

        self.assertEqual(result['total'], 20)
        self.assertEqual(result['success'], 20)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len(result['results']), 20)

        # Verify all files were created
        for res in result['results']:
            self.assertTrue(os.path.exists(res['output_path']))

if __name__ == '__main__':
    unittest.main()
