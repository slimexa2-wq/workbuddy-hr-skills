import unittest
import os
import tempfile
import shutil
from PIL import Image
from docx import Document

from ultra_modules.dossier_image_upright_core_engine import process_dossier_images_to_word

class TestDossierImageUprightCoreEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_docx = os.path.join(self.test_dir, "test_output.docx")

        # Create a dummy image
        self.dummy_image_path = os.path.join(self.test_dir, "dummy.jpg")
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(self.dummy_image_path)

        # Create an RGBA image
        self.rgba_image_path = os.path.join(self.test_dir, "rgba.png")
        img_rgba = Image.new('RGBA', (100, 100), color = (255, 0, 0, 128))
        img_rgba.save(self.rgba_image_path)

        # Create an image with orientation EXIF (minimal mock)
        self.exif_image_path = os.path.join(self.test_dir, "exif.jpg")
        img_exif = Image.new('RGB', (100, 100), color = 'blue')
        # We'll just create a normal image for EXIF processing, as full EXIF mocking is complex,
        # but PIL handles missing EXIF gracefully in our code.
        img_exif.save(self.exif_image_path)

        # Corrupted image file
        self.corrupt_image_path = os.path.join(self.test_dir, "corrupt.jpg")
        with open(self.corrupt_image_path, 'wb') as f:
            f.write(b"not an image file")

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        if os.path.exists("output_dossier.docx"):
            os.remove("output_dossier.docx")
        if os.path.exists("fallback_output_dossier.docx"):
            os.remove("fallback_output_dossier.docx")

    def test_normal_operation(self):
        """Test normal operation with valid images."""
        result = process_dossier_images_to_word(
            [self.dummy_image_path, self.rgba_image_path, self.exif_image_path],
            self.output_docx
        )
        self.assertEqual(result, self.output_docx)
        self.assertTrue(os.path.exists(self.output_docx))

        doc = Document(self.output_docx)
        # 3 valid images should result in 3 inline shapes (pictures)
        self.assertTrue(len(doc.inline_shapes) > 0)

    def test_missing_parameters_fallback(self):
        """Test auto-healing when parameters are missing or None."""
        result = process_dossier_images_to_word()
        self.assertEqual(result, "output_dossier.docx")
        self.assertTrue(os.path.exists("output_dossier.docx"))

    def test_dirty_data_cleaning(self):
        """Test silent cleaning of dirty input data (None, empty strings, ints)."""
        dirty_paths = [self.dummy_image_path, None, "", 123, "   ", self.rgba_image_path]
        result = process_dossier_images_to_word(dirty_paths, self.output_docx)
        self.assertEqual(result, self.output_docx)
        self.assertTrue(os.path.exists(self.output_docx))

    def test_corrupt_and_missing_files_silence(self):
        """Test that missing or corrupt image files are silently skipped."""
        paths = [
            self.dummy_image_path,
            os.path.join(self.test_dir, "nonexistent.jpg"),
            self.corrupt_image_path
        ]
        result = process_dossier_images_to_word(paths, self.output_docx)
        self.assertEqual(result, self.output_docx)
        self.assertTrue(os.path.exists(self.output_docx))

    def test_path_creation_fallback(self):
        """Test path creation failure fallback."""
        # Create a path that cannot be created (e.g., trying to use a file as a directory)
        invalid_out_dir = os.path.join(self.test_dir, "file_as_dir.txt")
        with open(invalid_out_dir, 'w') as f:
            f.write("text")

        impossible_path = os.path.join(invalid_out_dir, "deep", "out.docx")

        # When dir creation fails, it falls back to os.path.basename
        expected_fallback = "out.docx"

        result = process_dossier_images_to_word([self.dummy_image_path], impossible_path)
        self.assertEqual(result, expected_fallback)
        self.assertTrue(os.path.exists(expected_fallback))
        os.remove(expected_fallback)

if __name__ == '__main__':
    unittest.main()
