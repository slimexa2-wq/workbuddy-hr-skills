import unittest
import os
import math
import tempfile
from PIL import Image
from ultra_modules.dossier_image_upright_export_formatter import format_dossier

class TestDossierImageUprightExportFormatter(unittest.TestCase):
    def setUp(self):
        # Create a temporary test image
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_img_path = os.path.join(self.temp_dir.name, "test_img.jpg")
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(self.test_img_path)

        self.output_docx = os.path.join(self.temp_dir.name, "output.docx")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normal_execution(self):
        """Test 1: Normal execution with valid image and data"""
        extra_data = {"name": "张三", "department": "HR"}
        result = format_dossier([self.test_img_path], self.output_docx, extra_data)

        self.assertIn("已处理图片: 1张", result["report"])
        self.assertTrue(os.path.exists(result["docx_path"]))
        self.assertEqual(result["data"]["name"], "张三")
        self.assertEqual(result["data"]["comments"], 0)

    def test_missing_parameter_fallback(self):
        """Test 2: Missing parameters (None) fallback to defaults silently"""
        # Pass None for all arguments
        cwd = os.getcwd()
        default_docx_path = os.path.join(cwd, "dossier_output.docx")

        # Ensure we don't accidentally use a pre-existing file in assertion
        if os.path.exists(default_docx_path):
            os.remove(default_docx_path)

        result = format_dossier(None, None, None)

        self.assertIn("已处理图片: 0张", result["report"])
        self.assertEqual(result["docx_path"], "dossier_output.docx")
        self.assertEqual(result["data"]["comments"], 0)

        if os.path.exists(default_docx_path):
            os.remove(default_docx_path) # Clean up default output

    def test_dirty_data_self_healing(self):
        """Test 3: Dirty data self-healing with invalid paths"""
        invalid_paths = ["non_existent_file.jpg", "also_fake.png", self.test_img_path]
        result = format_dossier(invalid_paths, self.output_docx, {})

        # Should process 1 valid image, silently skip 2 invalid ones
        self.assertIn("已处理图片: 1张", result["report"])
        self.assertTrue(os.path.exists(self.output_docx))

    def test_nan_none_sanitization(self):
        """Test 4: NaN and None sanitization in extra_data"""
        dirty_data = {
            "valid_key": "value",
            "null_key": None,
            "nan_key": float('nan'),
            "comments": 5 # Should be overridden to 0
        }

        result = format_dossier([], self.output_docx, dirty_data)

        self.assertEqual(result["data"]["null_key"], "")
        self.assertEqual(result["data"]["nan_key"], 0.0)
        self.assertEqual(result["data"]["comments"], 0)
        self.assertFalse(math.isnan(result["data"]["nan_key"]))

    def test_extreme_boundaries(self):
        """Test 5: Extreme boundaries (empty strings, huge names)"""
        boundary_data = {
            "empty": "",
            "huge_name": "张三" * 1000,
            "weird_type": [1, 2, 3]
        }

        # Empty image paths, very long docx path
        long_docx_path = os.path.join(self.temp_dir.name, "a" * 100 + ".docx")
        result = format_dossier([], long_docx_path, boundary_data)

        self.assertIn("已处理图片: 0张", result["report"])
        self.assertEqual(result["data"]["huge_name"], "张三" * 1000)
        self.assertEqual(result["data"]["weird_type"], [1, 2, 3])
        self.assertTrue(os.path.exists(long_docx_path))

if __name__ == '__main__':
    unittest.main()
