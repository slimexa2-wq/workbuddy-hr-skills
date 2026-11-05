import os
import unittest
import tempfile
import shutil
from PIL import Image, ExifTags
from ultra_modules.dossier_image_upright_audit_trace import process_dossier, AuditLogger, _get_file_hash, _correct_image_orientation

class TestDossierImageUprightAuditTrace(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.image_paths = []

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_test_image(self, filename, orientation=1, invalid=False, text_file=False):
        filepath = os.path.join(self.test_dir, filename)

        if invalid:
            with open(filepath, 'wb') as f:
                f.write(b"not an image file")
            return filepath

        if text_file:
            with open(filepath, 'w') as f:
                f.write("Just some text")
            return filepath

        img = Image.new('RGB', (100, 100), color = 'red')

        if orientation != 1:
            # Need to get orientation tag key
            orientation_tag = None
            for key, val in ExifTags.TAGS.items():
                if val == 'Orientation':
                    orientation_tag = key
                    break

            if orientation_tag:
                exif = img.getexif()
                exif[orientation_tag] = orientation
                img.save(filepath, exif=exif)
                return filepath

        img.save(filepath)
        return filepath

    # 1. Normal Operation (including EXIF rotation logic 3, 6, 8)
    def test_normal_operation_and_exif_rotation(self):
        # Normal image
        img1 = self._create_test_image("img1.jpg", orientation=1)
        # Rotated images (3: 180, 6: 270, 8: 90)
        img3 = self._create_test_image("img3.jpg", orientation=3)
        img6 = self._create_test_image("img6.jpg", orientation=6)
        img8 = self._create_test_image("img8.jpg", orientation=8)

        result = process_dossier([img1, img3, img6, img8])

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed_count"], 4)
        self.assertEqual(result["deduplicated_count"], 0)
        self.assertTrue(os.path.exists(result["output_path"]))

        # Check audit logs for rotations
        logs = result["audit_logs"]
        rotation_logs = [log for log in logs if log["action"] == "exif_correction"]
        self.assertEqual(len(rotation_logs), 4)
        actions = [log["details"]["action"] for log in rotation_logs]
        self.assertIn("no rotation needed", actions)
        self.assertIn("rotated 180", actions)
        self.assertIn("rotated 270", actions)
        self.assertIn("rotated 90", actions)

        os.remove(result["output_path"])

    # 2. Dirty Data (Invalid files, non-existent files, non-string paths)
    def test_dirty_data_self_healing(self):
        valid_img = self._create_test_image("valid.jpg")
        invalid_img = self._create_test_image("invalid.jpg", invalid=True)
        text_img = self._create_test_image("text.txt", text_file=True)

        paths = [
            valid_img,
            "nonexistent.jpg",
            123,  # non-string
            invalid_img,
            text_img
        ]

        result = process_dossier(paths)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed_count"], 1) # Only valid_img works
        self.assertTrue(os.path.exists(result["output_path"]))

        # Verify dirty data was logged
        logs = result["audit_logs"]
        skipped_logs = [log for log in logs if log["action"] == "dirty_data_skipped"]
        self.assertEqual(len(skipped_logs), 2) # nonexistent, and 123

        error_logs = [log for log in logs if log["action"] == "exif_correction_error"]
        self.assertEqual(len(error_logs), 2) # invalid.jpg and text.txt will fail Pillow open

        os.remove(result["output_path"])

    # 3. Missing parameter defaults
    def test_missing_parameter_defaults(self):
        result = process_dossier() # No args
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed_count"], 0)
        self.assertTrue(os.path.exists(result["output_path"]))

        # Check logs
        logs = result["audit_logs"]
        default_log = [log for log in logs if log["action"] == "default_parameter_applied"]
        self.assertEqual(len(default_log), 1)
        self.assertEqual(default_log[0]["details"]["parameter"], "output_docx_path")

        os.remove(result["output_path"])

    # 4. Deduplication logic
    def test_deduplication(self):
        img1 = self._create_test_image("img1.jpg")
        # Exact copy
        img1_copy = os.path.join(self.test_dir, "img1_copy.jpg")
        shutil.copy2(img1, img1_copy)

        result = process_dossier([img1, img1_copy])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(result["deduplicated_count"], 1)

        logs = result["audit_logs"]
        dedup_logs = [log for log in logs if log["action"] == "deduplication"]
        self.assertEqual(len(dedup_logs), 1)

        os.remove(result["output_path"])

    # 5. Extreme boundary: Empty list
    def test_extreme_boundary_empty_list(self):
        result = process_dossier([])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed_count"], 0)
        self.assertTrue(os.path.exists(result["output_path"]))
        os.remove(result["output_path"])

    # 6. Test specific methods and errors
    def test_get_file_hash_nonexistent(self):
        self.assertEqual(_get_file_hash("nonexistent_file_123.jpg"), "")

    def test_fatal_error_handling(self):
        # We can force a fatal error by passing an invalid output path like a directory
        img = self._create_test_image("img.jpg")
        result = process_dossier([img], output_docx_path=self.test_dir)
        self.assertEqual(result["status"], "error")
        # Word compilation error should occur trying to save to a directory

    def test_cleanup_error(self):
        # To hit the cleanup error, we can make os.remove fail
        import unittest.mock as mock
        with mock.patch('os.remove', side_effect=Exception("Mock remove error")):
            img = self._create_test_image("img.jpg")
            result = process_dossier([img])

            logs = result["audit_logs"]
            cleanup_errors = [log for log in logs if log["action"] == "cleanup_error"]
            self.assertEqual(len(cleanup_errors), 1)

    def test_cleanup_file_not_exists(self):
        # Test when file doesn't exist during cleanup
        import unittest.mock as mock
        img = self._create_test_image("img.jpg")
        with mock.patch('os.path.exists', side_effect=lambda x: False if x.endswith('.jpg') and not x.endswith('img.jpg') else True):
            result = process_dossier([img])
            self.assertEqual(result["status"], "success")

    def test_orientation_no_tag(self):
        import unittest.mock as mock
        img = self._create_test_image("img_no_tag.jpg")
        with mock.patch('PIL.ExifTags.TAGS', {}):
            result = process_dossier([img])
            self.assertEqual(result["status"], "success")

    def test_exif_none(self):
        import unittest.mock as mock
        img = self._create_test_image("img_no_exif.jpg")
        with mock.patch('PIL.Image.Image.getexif', return_value=None):
            result = process_dossier([img])
            self.assertEqual(result["status"], "success")

    def test_word_compilation_error(self):
        import unittest.mock as mock
        # docx.Document is actually a factory function, we need to mock the document object's method
        with mock.patch('docx.document.Document.add_picture', side_effect=Exception("Mock add_picture error")):
            img = self._create_test_image("img.jpg")
            result = process_dossier([img])
            logs = result["audit_logs"]
            comp_errors = [log for log in logs if log["action"] == "word_compilation_error"]
            self.assertEqual(len(comp_errors), 1)

if __name__ == '__main__':
    unittest.main()
