import unittest
import io
import json
from PIL import Image, ExifTags
from docx import Document
from ultra_modules.dossier_image_upright_plain_explainer import process_dossier

class TestDossierImageUprightPlainExplainer(unittest.TestCase):

    def setUp(self):
        # Create a simple test image in memory
        img = Image.new('RGB', (100, 50), color='blue')
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        self.normal_image_bytes = img_byte_arr.getvalue()

        # Create an image with EXIF rotation
        # Note: Pillow's Exif manipulation is a bit complex for simple test setup,
        # but we can mock or use a workaround if needed. For now, creating a fake EXIF dict
        # and mocking the _getexif method is the most reliable way to test the logic.
        pass

    def test_missing_data_default_behavior(self):
        """Test missing data falls back gracefully (缺参默认兜底)"""
        # Call with no args at all
        res = process_dossier()

        # Default output format is JSON (dict)
        self.assertIsInstance(res, dict)
        self.assertEqual(res['status'], 'error')
        self.assertEqual(res['message'], '未提供图片数据')
        self.assertEqual(res['title'], '新员工入职资料处理报告')
        self.assertFalse(res['details']['rotated'])
        self.assertEqual(res['details']['final_width'], 0)

    def test_dirty_data_self_healing(self):
        """Test with corrupt or unsupported image data (脏数据自愈)"""
        dirty_bytes = b"not_an_image_at_all_just_random_garbage"

        res = process_dossier(image_data=dirty_bytes, output_format="md")

        # Output format is Markdown
        self.assertIsInstance(res, str)
        self.assertIn("error", res)
        self.assertIn("图片处理失败", res)

    def test_normal_image_processing_json(self):
        """Test processing a normal image with JSON output (正常处理)"""
        res = process_dossier(
            image_data=self.normal_image_bytes,
            output_format="json",
            title="Custom Title"
        )

        self.assertIsInstance(res, dict)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['title'], 'Custom Title')
        self.assertEqual(res['message'], '图片处理成功')
        self.assertEqual(res['details']['final_width'], 100)
        self.assertEqual(res['details']['final_height'], 50)
        self.assertFalse(res['details']['rotated'])

    def test_html_output_format(self):
        """Test generating HTML output (大白话可视化卡片)"""
        res = process_dossier(
            image_data=self.normal_image_bytes,
            output_format="html"
        )

        self.assertIsInstance(res, str)
        self.assertIn("<div class=\"dossier-card\"", res)
        self.assertIn("图片处理成功", res)
        self.assertIn("success", res)

    def test_word_embedding_extreme_boundary(self):
        """Test embedding output into a Word document (Word高清排版)"""
        word_bytes = process_dossier(
            image_data=self.normal_image_bytes,
            embed_in_word=True
        )

        # Should return raw docx bytes
        self.assertIsInstance(word_bytes, bytes)

        # Let's try to open it with python-docx to verify it's a valid Word doc
        doc = Document(io.BytesIO(word_bytes))
        paragraphs_text = [p.text for p in doc.paragraphs]

        self.assertIn("新员工入职资料处理报告", paragraphs_text)
        self.assertIn("图片处理成功", paragraphs_text)
        self.assertIn("图像尺寸：100 x 50", paragraphs_text)

    def test_exif_rotation_simulation(self):
        """Test that EXIF rotation logic works (旋转纠正)"""
        img = Image.new('RGB', (100, 50), color='blue')

        # We'll monkeypatch the image open inside the function or just test the logic directly
        # To make it isolated, we'll patch Image.open to return an image with a fake _getexif
        import sys

        class FakeExifImage(Image.Image):
            def _getexif(self):
                # Orientation is tag 274
                return {274: 6} # 6 means rotated 270 degrees

            def convert(self, mode):
                return self

            def rotate(self, angle, expand=False):
                # Simulated rotation
                rotated_img = Image.new('RGB', (50, 100), color='blue')
                return rotated_img

            def save(self, fp, format=None, **params):
                fp.write(b"fake_rotated_bytes")

        # Patch Image.open
        original_open = Image.open

        def mock_open(*args, **kwargs):
            img = Image.new('RGB', (100, 50), color='blue')
            img.__class__ = FakeExifImage
            return img

        try:
            import ultra_modules.dossier_image_upright_plain_explainer as module
            module.Image.open = mock_open
            res = process_dossier(image_data=b"trigger_mock", output_format="json")

            if res['status'] != 'success':
                print(res['message'])
            self.assertEqual(res['status'], 'success')
            self.assertTrue(res['details']['rotated'])
            self.assertEqual(res['message'], '图片处理成功（自动正立）')

        finally:
            import ultra_modules.dossier_image_upright_plain_explainer as module
            module.Image.open = original_open

    def test_invalid_output_format_fallback(self):
        """Test fallback when an invalid output format is provided"""
        res = process_dossier(image_data=self.normal_image_bytes, output_format="invalid_format")

        # Should fallback to JSON dictionary
        self.assertIsInstance(res, dict)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['details']['final_width'], 100)

    def test_word_embed_failure_fallback(self):
        """Test fallback when Word embedding fails (e.g. image bytes are missing but success is True, which shouldn't happen, but we can simulate by forcing a failure in docx creation)"""
        # Patch Document to raise an exception
        import ultra_modules.dossier_image_upright_plain_explainer as module
        original_doc = module.Document

        def mock_document(*args, **kwargs):
            raise Exception("Word generation failed")

        try:
            module.Document = mock_document
            res = process_dossier(image_data=self.normal_image_bytes, embed_in_word=True, output_format="json")

            # Should fallback to regular output format since Word embedding failed
            self.assertIsInstance(res, dict)
            self.assertEqual(res['status'], 'success')
        finally:
            module.Document = original_doc

if __name__ == '__main__':
    unittest.main()
