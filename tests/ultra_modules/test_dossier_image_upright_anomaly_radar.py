import unittest
import os
import tempfile
import shutil
from PIL import Image, ExifTags
from docx import Document
from ultra_modules.dossier_image_upright_anomaly_radar import DossierRadar

class TestDossierRadar(unittest.TestCase):
    def setUp(self):
        self.radar = DossierRadar()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_dummy_image(self, filename: str, size: int = 100, orientation: int = None) -> str:
        """Helper to create a dummy image with optional EXIF orientation."""
        filepath = os.path.join(self.test_dir, filename)
        img = Image.new('RGB', (100, 100), color='white')

        exif = None
        if orientation is not None:
            try:
                exif = img.getexif()
                exif[self.radar._ORIENTATION_TAG] = orientation
            except Exception:
                pass

        if exif:
            img.save(filepath, format='JPEG', exif=exif)
        else:
            img.save(filepath, format='JPEG')

        # If we need a specific size for testing anomalies, we append dummy data
        if size > 100:
            with open(filepath, 'a') as f:
                # Write some spaces to artificially increase file size
                f.write(' ' * (size - os.path.getsize(filepath)))

        return filepath

    def test_normal_images_green_flag(self):
        """Test that a small list of similarly sized items gets green flags."""
        items = [
            {'path': '1.jpg', 'size': 1000},
            {'path': '2.jpg', 'size': 1050},
            {'path': '3.jpg', 'size': 950}
        ]
        analyzed = self.radar.detect_anomalies(items)
        for item in analyzed:
            self.assertEqual(item['flag'], 'Green')
            self.assertEqual(item['reason'], '正常')

    def test_dirty_data_self_healing_exif(self):
        """Test handling of broken or missing EXIF data."""
        # Create an image without EXIF
        img_path = self._create_dummy_image('no_exif.jpg')
        with Image.open(img_path) as img:
            # Should return the image unchanged without throwing an error
            corrected_img = self.radar.correct_exif_rotation(img)
            self.assertIsNotNone(corrected_img)

        # Test with an image that has an orientation tag
        img_path_exif = self._create_dummy_image('exif.jpg', orientation=6) # 270 rotate
        with Image.open(img_path_exif) as img_exif:
            corrected_img_exif = self.radar.correct_exif_rotation(img_exif)
            self.assertIsNotNone(corrected_img_exif)
        # Check if the dimensions were swapped (100x100 so it doesn't matter much visually,
        # but we ensure the code path doesn't crash)

    def test_missing_params_default_fallback(self):
        """Test that missing 'size' defaults to 0 and doesn't crash."""
        items = [{'path': 'missing_size.jpg'}]
        analyzed = self.radar.detect_anomalies(items)
        self.assertEqual(analyzed[0]['size'], 0)
        self.assertEqual(analyzed[0]['flag'], 'Green')

        # Test process method with a non-existent file path
        report = self.radar.process(['non_existent.jpg'], os.path.join(self.test_dir, 'out.docx'))
        self.assertEqual(report['status'], 'success')
        self.assertEqual(report['items_analyzed'], 1)
        self.assertEqual(report['details'][0]['size'], 0)

    def test_extreme_boundary_empty_or_huge_images(self):
        """Test empty lists and extreme sizes."""
        # Empty list
        self.assertEqual(self.radar.detect_anomalies([]), [])

        # Extreme sizes
        items = [
            {'size': 0},       # Empty file
            {'size': 100},     # Normal
            {'size': 105},     # Normal
            {'size': 110},     # Normal
            {'size': 9999999}  # Huge
        ]

        analyzed = self.radar.detect_anomalies(items)
        # The 9999999 one should definitely be flagged
        huge_item = next(item for item in analyzed if item['size'] == 9999999)
        self.assertIn(huge_item['flag'], ['Red', 'Yellow'])

    def test_anomaly_detection_top_3_percent(self):
        """Test that it flags the top ~3%."""
        # Create 100 items. 3% is 3 items.
        items = [{'size': 1000 + i} for i in range(97)]
        # Add 3 extreme outliers
        items.extend([{'size': 50000}, {'size': 60000}, {'size': 70000}])

        analyzed = self.radar.detect_anomalies(items)

        flags = [item['flag'] for item in analyzed]
        anomalies = [flag for flag in flags if flag in ['Red', 'Yellow']]

        # We have 100 items, 3% is exactly 3.
        self.assertEqual(len(anomalies), 3)

        # Ensure the 3 anomalies are the ones we added
        for item in analyzed:
            if item['size'] >= 50000:
                self.assertIn(item['flag'], ['Red', 'Yellow'])
            else:
                self.assertEqual(item['flag'], 'Green')

    def test_process_generates_word_doc(self):
        """Test the end-to-end process method."""
        img1 = self._create_dummy_image('test1.jpg')
        img2 = self._create_dummy_image('test2.jpg')

        out_docx = os.path.join(self.test_dir, 'test_output.docx')

        report = self.radar.process([img1, img2], out_docx)

        self.assertEqual(report['status'], 'success')
        self.assertTrue(os.path.exists(out_docx))

        # Verify document contains images
        doc = Document(out_docx)
        self.assertGreater(len(doc.paragraphs), 0)

if __name__ == '__main__':
    unittest.main()
