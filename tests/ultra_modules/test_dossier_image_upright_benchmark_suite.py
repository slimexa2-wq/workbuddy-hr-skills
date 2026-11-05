import unittest
import os
import io
import time
from PIL import Image, ExifTags
from concurrent.futures import ThreadPoolExecutor
from ultra_modules.dossier_image_upright_benchmark_suite import fix_image_rotation, create_upright_dossier_word

class TestDossierImageUprightBenchmarkSuite(unittest.TestCase):
    def setUp(self):
        # Create a synthetic valid image for testing
        self.valid_img = Image.new('RGB', (100, 100), color = 'red')
        self.valid_img_bytes = io.BytesIO()
        self.valid_img.save(self.valid_img_bytes, format='JPEG')
        self.valid_img_bytes = self.valid_img_bytes.getvalue()

        # Temporary files to clean up
        self.temp_files = []

    def tearDown(self):
        for f in self.temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


    def test_normal_valid_image(self):
        output_path = "test_normal_output.docx"
        self.temp_files.append(output_path)

        # Test bytes
        res = create_upright_dossier_word([self.valid_img_bytes], output_path=output_path)
        self.assertEqual(res, output_path)
        self.assertTrue(os.path.exists(output_path))

        # Test string path
        img_path = "test_temp_img.jpg"
        self.temp_files.append(img_path)
        with open(img_path, 'wb') as f:
            f.write(self.valid_img_bytes)

        res2 = create_upright_dossier_word([img_path], output_path=output_path)
        self.assertEqual(res2, output_path)
        self.assertTrue(os.path.exists(output_path))

        # Test image with EXIF rotation
        # Note: PIL's Exif handling is a bit complex for synthesizing purely in-memory easily without saving/loading,
        # but we can mock or construct one to hit branches 3, 6, 8.
        class MockExif(dict):
            pass

        orientation_tag = None
        for k, v in ExifTags.TAGS.items():
            if v == 'Orientation':
                orientation_tag = k
                break

        for orientation in [3, 6, 8, 1, None]:
            img = Image.new('RGB', (100, 100), color = 'blue')
            if orientation:
                mock_exif = MockExif()
                mock_exif[orientation_tag] = orientation
                img._getexif = lambda: mock_exif

            fixed_img = fix_image_rotation(img)
            self.assertIsNotNone(fixed_img)


    def test_missing_parameters(self):
        # Should auto-default both image_sources and output_path
        res = create_upright_dossier_word()
        self.assertIsNotNone(res)
        self.temp_files.append(res)
        self.assertTrue(os.path.exists(res))
        self.assertTrue(res.startswith("dossier_output_"))
        self.assertTrue(res.endswith(".docx"))


    def test_dirty_data_resilience(self):
        output_path = "test_dirty_data.docx"
        self.temp_files.append(output_path)

        dirty_sources = [
            None,
            12345,
            "non_existent_file.xyz",
            b"corrupted_bytes_data",
            [1, 2, 3], # Invalid inner type
            self.valid_img_bytes # Valid one at the end to ensure it keeps processing
        ]

        res = create_upright_dossier_word(dirty_sources, output_path=output_path)
        self.assertEqual(res, output_path)
        self.assertTrue(os.path.exists(output_path))

        # Test EXIF exception handling
        img = Image.new('RGB', (100, 100))
        img._getexif = lambda: "not a dict" # Will throw exception on 'in' check
        fixed_img = fix_image_rotation(img)
        self.assertEqual(img, fixed_img) # Should return original silently

        # Test image mode not RGB/RGBA
        img_p = Image.new('P', (100, 100))
        img_p_bytes = io.BytesIO()
        img_p.save(img_p_bytes, format='PNG')
        res_p = create_upright_dossier_word([img_p_bytes.getvalue()], output_path=output_path)
        self.assertEqual(res_p, output_path)


    def test_invalid_output_path(self):
        # A path that is a directory instead of file, or write-protected
        invalid_path = "/" # Root dir is not writable as file
        res = create_upright_dossier_word([self.valid_img_bytes], output_path=invalid_path)
        self.assertIsNone(res) # Should gracefully return None


    def test_extreme_concurrency(self):
        concurrency = 50
        results = []

        def run_task(i):
            path = f"test_concurrent_{i}.docx"
            self.temp_files.append(path)
            start_time = time.time()
            res = create_upright_dossier_word([self.valid_img_bytes], output_path=path)
            duration = time.time() - start_time
            return res, duration

        with ThreadPoolExecutor(max_workers=10) as executor:
            for res, duration in executor.map(run_task, range(concurrency)):
                results.append((res, duration))

        for res, duration in results:
            self.assertIsNotNone(res)
            self.assertTrue(os.path.exists(res))
            # Ensure roughly fast response per task
            self.assertTrue(duration < 1.0) # Should be well within 1000ms


    def test_exif_coverage_cases(self):
        # Additional EXIF coverage
        # Hit orientation not in keys
        img = Image.new('RGB', (100, 100))
        img._getexif = lambda: {"dummy": 1}
        fix_image_rotation(img)

        # Hit exception during rotation
        class MockImage:
            def __init__(self):
                pass
            def _getexif(self):
                return {274: 3} # 274 is usually the Orientation tag
            def rotate(self, *args, **kwargs):
                raise ValueError("mock rotation error")
        fix_image_rotation(MockImage())

        # Hit no ExifTags.TAGS match
        import PIL.ExifTags
        old_tags = PIL.ExifTags.TAGS
        PIL.ExifTags.TAGS = {}
        img3 = Image.new('RGB', (100, 100))
        img3._getexif = lambda: {274: 3}
        fix_image_rotation(img3)
        PIL.ExifTags.TAGS = old_tags

if __name__ == '__main__':
    unittest.main()
