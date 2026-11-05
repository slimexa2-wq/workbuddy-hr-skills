import os
import unittest
import tempfile
import shutil
from unittest.mock import patch
from PIL import Image
from ultra_modules.dossier_image_upright_integration_bridge import DossierImageUprightIntegrationBridge

class TestDossierImageUprightIntegrationBridge(unittest.TestCase):
    def setUp(self):
        # Setup temporary directory for test isolation
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create some dummy image files to test core engine interaction
        self.img1_path = "test1.jpg"
        self.img2_path = "test2.png"

        img = Image.new('RGB', (10, 10), color='red')
        # Add fake EXIF orientation tag if needed, but not strictly required for test
        img.save(self.img1_path)
        img.save(self.img2_path)

    def tearDown(self):
        # Restore cwd and remove temp directory
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_normal_schema_v1_flat(self):
        # Case 1: Normal input schema v1 (flat dict)
        payload = {
            "images": [self.img1_path, self.img2_path],
            "output_file": "v1_output.docx"
        }

        output_path = DossierImageUprightIntegrationBridge.process_payload(payload)

        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "v1_output.docx")

    def test_nested_schema_v2_and_auto_deduplication(self):
        # Case 2: Nested schema v2 with duplicate dirty data
        payload = {
            "meta": {
                "version": "v2",
                "vendor_data": {
                    "docs": {
                        "final_path": "v2_nested_output.docx",
                        "extra_info": [self.img1_path]
                    }
                }
            },
            "payload_data": {
                "attachments": [self.img1_path, self.img2_path, self.img2_path, "    ", None, ""]
            }
        }

        output_path = DossierImageUprightIntegrationBridge.process_payload(payload)
        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "v2_nested_output.docx")

    def test_dirty_data_self_healing(self):
        # Case 3: Dirty data self healing (mixed lists, dictionaries with odd types)
        payload = {
            "unexpected_list": [123, {"nested_img": self.img2_path}, 45.6],
            "random_image_field": self.img1_path,
            "null_value": None,
            "export_doc": "healed_output.docx",
            "boolean": True
        }

        output_path = DossierImageUprightIntegrationBridge.process_payload(payload)
        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "healed_output.docx")

    def test_missing_parameter_default_fallback(self):
        # Case 4: Missing parameters default fallback (no output docx provided)
        payload = {
            "photos": [self.img1_path]
        }

        output_path = DossierImageUprightIntegrationBridge.process_payload(payload)
        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "output_dossier.docx")

    def test_extreme_boundary_cases(self):
        # Case 5: Extreme boundaries (none, random string, random list, empty dict)

        # Test passing string directly instead of payload dict
        output_path = DossierImageUprightIntegrationBridge.process_payload(self.img1_path)
        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "output_dossier.docx")

        # Test passing list directly
        output_path = DossierImageUprightIntegrationBridge.process_payload([self.img2_path])
        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "output_dossier.docx")

        # Test passing completely unexpected type (e.g. None or Integer)
        output_path = DossierImageUprightIntegrationBridge.process_payload(None)
        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "output_dossier.docx")

        # Test empty dict
        output_path = DossierImageUprightIntegrationBridge.process_payload({})
        self.assertIsNotNone(output_path)
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(os.path.basename(output_path), "output_dossier.docx")

if __name__ == '__main__':
    unittest.main()
