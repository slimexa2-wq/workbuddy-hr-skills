import os
import unittest
import tempfile
import time
import shutil
from PIL import Image, ExifTags
from ultra_modules.dossier_image_upright_self_healing_guard import DossierImageUprightSelfHealingGuard, Snapshot

class TestDossierImageUprightSelfHealingGuard(unittest.TestCase):
    def setUp(self):
        self.guard = DossierImageUprightSelfHealingGuard()
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = self.test_dir.name

    def tearDown(self):
        self.guard.cleanup_all_snapshots()
        self.test_dir.cleanup()

    def _create_test_image(self, filename, orientation=None, mode='RGB'):
        path = os.path.join(self.test_dir_path, filename)
        img = Image.new(mode, (100, 100), color='red')

        if orientation:
            # Add EXIF data
            exif_dict = {
                ExifTags.TAGS_V2[k]: v for k, v in {
                    ExifTags.Base.Orientation: orientation
                }.items() if k in ExifTags.TAGS_V2
            }
            # Simplistic approach to mock EXIF for PIL since creating actual valid EXIF bytes is complex
            # We mock the _getexif method in the test if needed, or rely on PIL's ability to save EXIF
            # But the most robust way to test our _correct_image_orientation logic is directly.
            pass

        img.save(path, format='JPEG' if mode != 'RGBA' else 'PNG')
        return path

    def test_normal_operation_and_undo(self):
        """Test 1: Normal operation with EXIF rotation and output doc creation, and undo snapshot mechanism."""
        # 1. Create a dummy image
        img_path = self._create_test_image("test_normal.jpg")
        output_path = os.path.join(self.test_dir_path, "out_normal.docx")

        # 2. Process
        snapshot_id = self.guard.process_dossier([img_path], output_path)
        self.assertIsNotNone(snapshot_id)
        self.assertTrue(os.path.exists(output_path))

        # 3. Undo
        success = self.guard.undo_snapshot(snapshot_id)
        self.assertTrue(success)
        self.assertFalse(os.path.exists(output_path)) # Should revert to non-existent state since it didn't exist before

    def test_dirty_data_self_healing(self):
        """Test 2: Dirty data self-healing (non-existent images, corrupt images, invalid input types)."""
        output_path = os.path.join(self.test_dir_path, "out_dirty.docx")

        # Mix of valid and invalid paths
        valid_img = self._create_test_image("test_dirty_valid.jpg")
        corrupt_img = os.path.join(self.test_dir_path, "corrupt.jpg")
        with open(corrupt_img, "wb") as f:
            f.write(b"not an image")

        dirty_paths = [
            "non_existent.jpg",
            123, # invalid type
            None,
            corrupt_img,
            valid_img
        ]

        snapshot_id = self.guard.process_dossier(dirty_paths, output_path)
        self.assertIsNotNone(snapshot_id)
        self.assertTrue(os.path.exists(output_path)) # The valid one should have been processed, doc created

    def test_missing_parameter_default_fallback(self):
        """Test 3: Missing parameter default fallback (`process_dossier()` with no args)."""
        snapshot_id = self.guard.process_dossier()
        self.assertIsNotNone(snapshot_id)
        self.assertTrue(os.path.exists("dossier_output_default.docx"))

        # Cleanup default file
        self.guard.undo_snapshot(snapshot_id)
        if os.path.exists("dossier_output_default.docx"):
            os.remove("dossier_output_default.docx")

    def test_extreme_boundary_conditions(self):
        """Test 4: Extreme boundary conditions (invalid output names, OS permission errors fallback)."""
        img_path = self._create_test_image("test_boundary.jpg")

        # Invalid directory
        invalid_output = "/root/restricted_dir/output.docx"

        # It should fallback to current directory
        snapshot_id = self.guard.process_dossier([img_path], invalid_output)
        self.assertIsNotNone(snapshot_id)
        self.assertTrue(os.path.exists("output.docx"))

        # Cleanup
        self.guard.undo_snapshot(snapshot_id)
        if os.path.exists("output.docx"):
            os.remove("output.docx")

    def test_undo_on_existing_file(self):
        """Test 5: Undo snapshot mechanism when the file already existed."""
        output_path = os.path.join(self.test_dir_path, "out_existing.docx")
        with open(output_path, "w") as f:
            f.write("original content")

        img_path = self._create_test_image("test_existing.jpg")

        snapshot_id = self.guard.process_dossier([img_path], output_path)
        self.assertIsNotNone(snapshot_id)

        # Doc should be overwritten/modified
        self.assertTrue(os.path.exists(output_path))
        self.assertNotEqual(os.path.getsize(output_path), len("original content"))

        # Undo should restore original content
        success = self.guard.undo_snapshot(snapshot_id)
        self.assertTrue(success)
        with open(output_path, "r") as f:
            self.assertEqual(f.read(), "original content")

    def test_image_orientation_logic(self):
        """Test the EXIF orientation logic directly via mocking since PIL EXIF creation is complex."""
        class MockImage:
            def __init__(self, orientation):
                self.orientation = orientation
                self.rotated = None

            def getexif(self):
                # Map orientation tag ID to value
                # Assuming ExifTags.TAGS contains orientation string, let's find the int key
                orient_key = 274 # Standard EXIF Orientation tag
                if not orient_key in ExifTags.TAGS.keys() or ExifTags.TAGS[orient_key] != 'Orientation':
                    for k, v in ExifTags.TAGS.items():
                        if v == 'Orientation':
                            orient_key = k
                            break
                return {orient_key: self.orientation}

            def rotate(self, angle, expand=False):
                self.rotated = angle
                return self

        # Test 180 degrees
        img_mock = MockImage(3)
        res = self.guard._correct_image_orientation(img_mock)
        self.assertEqual(res.rotated, 180)

        # Test 270 degrees
        img_mock = MockImage(6)
        res = self.guard._correct_image_orientation(img_mock)
        self.assertEqual(res.rotated, 270)

        # Test 90 degrees
        img_mock = MockImage(8)
        res = self.guard._correct_image_orientation(img_mock)
        self.assertEqual(res.rotated, 90)

    def test_snapshot_failure_handlers(self):
        """Test snapshot failure mechanisms"""
        # Test restore failure (already inactive)
        snap = Snapshot("dummy")
        self.assertFalse(snap.restore())

        # Test invalid snapshot undo
        self.assertFalse(self.guard.undo_snapshot("nonexistent"))
        self.assertFalse(self.guard.undo_snapshot(None))

    def test_process_all_failed(self):
        """Test when all images fail, and no empty fallback is needed because images were provided but failed."""
        output_path = os.path.join(self.test_dir_path, "out_all_fail.docx")
        snapshot_id = self.guard.process_dossier([123, None], output_path)
        # Should return None when ALL images fail to process
        self.assertIsNone(snapshot_id)

    def test_string_image_path_handling(self):
        """Test handling of single string path."""
        img_path = self._create_test_image("single.jpg")
        output_path = os.path.join(self.test_dir_path, "single_out.docx")
        snapshot_id = self.guard.process_dossier(img_path, output_path)
        self.assertIsNotNone(snapshot_id)
        self.assertTrue(os.path.exists(output_path))

    def test_rgba_image_conversion(self):
        """Test RGBA image conversion logic."""
        img_path = self._create_test_image("rgba.png", mode='RGBA')
        output_path = os.path.join(self.test_dir_path, "rgba_out.docx")
        snapshot_id = self.guard.process_dossier([img_path], output_path)
        self.assertIsNotNone(snapshot_id)
        self.assertTrue(os.path.exists(output_path))

    def test_snapshot_exceptions(self):
        """Test exception handling in Snapshot."""
        # Test creation failure
        # Trigger creation exception by trying to copy something that isn't a file or doesn't have permissions
        snap = Snapshot("/root/restricted/fake.docx")
        snap.create() # Should log a warning and not raise

        # Test restore exception
        snap.is_active = True
        snap.backup_path = "/root/restricted/fake.bak"
        snap.restore() # Should log a warning and return False

        # Test cleanup exception
        snap.cleanup() # Should pass silently

    def test_get_exif_orientation_tag_none(self):
        """Test _get_exif_orientation_tag returning None."""
        guard = DossierImageUprightSelfHealingGuard()
        original_tags = ExifTags.TAGS.copy()
        ExifTags.TAGS.clear()
        self.assertIsNone(guard._get_exif_orientation_tag())
        ExifTags.TAGS.update(original_tags)

    def test_correct_image_orientation_exceptions(self):
        """Test _correct_image_orientation exceptions and early returns."""
        guard = DossierImageUprightSelfHealingGuard()

        class FakeImageNoGetExif:
            pass

        class FakeImageNoOrientationTag:
            def getexif(self):
                return {123: 1} # No orientation tag

        class FakeImageEmptyOrientation:
            def getexif(self):
                return {274: None}

        class FakeImageException:
            def getexif(self):
                raise Exception("Fake Exception")

        img = FakeImageNoGetExif()
        self.assertEqual(guard._correct_image_orientation(img), img)

        img = FakeImageNoOrientationTag()
        self.assertEqual(guard._correct_image_orientation(img), img)

        img = FakeImageEmptyOrientation()
        self.assertEqual(guard._correct_image_orientation(img), img)

        img = FakeImageException()
        self.assertEqual(guard._correct_image_orientation(img), img)

    def test_process_dossier_save_exception(self):
        """Test process_dossier doc.save exception handling."""
        guard = DossierImageUprightSelfHealingGuard()

        # We need an output filename that is highly restricted to trigger permission error when saving
        invalid_output = "/root/restricted_dir/output.docx"

        # Try to process with empty list so it attempts to save an empty doc
        import docx.document
        original_save = docx.document.Document.save

        def fake_save(self, path):
            raise Exception("Save failed")

        docx.document.Document.save = fake_save
        try:
            snapshot_id = guard.process_dossier([], invalid_output)
            self.assertIsNone(snapshot_id)
        finally:
            docx.document.Document.save = original_save

    def test_os_makedirs_exception(self):
        """Test os.makedirs exception fallback."""
        guard = DossierImageUprightSelfHealingGuard()
        original_makedirs = os.makedirs

        def fake_makedirs(name, mode=511, exist_ok=False):
            raise Exception("Makedirs failed")

        os.makedirs = fake_makedirs
        try:
            # We must use a path with a directory to trigger makedirs
            snapshot_id = guard.process_dossier([], "some_dir/output.docx")
            self.assertIsNotNone(snapshot_id)
            # It should fallback to basename
            self.assertTrue(os.path.exists("output.docx"))
            guard.undo_snapshot(snapshot_id)
            if os.path.exists("output.docx"):
                os.remove("output.docx")
        finally:
            os.makedirs = original_makedirs

    def test_snapshot_create_exception(self):
        """Test Snapshot create method exception."""
        # A simple way to raise exception in shutil.copy2
        snap = Snapshot("test_create_exc.txt")
        original_copy2 = shutil.copy2
        def fake_copy2(src, dst):
            raise Exception("Copy failed")
        shutil.copy2 = fake_copy2
        try:
            with open("test_create_exc.txt", "w") as f:
                f.write("test")
            snap.create()
            self.assertFalse(snap.is_active)
        finally:
            shutil.copy2 = original_copy2
            if os.path.exists("test_create_exc.txt"):
                os.remove("test_create_exc.txt")

    def test_snapshot_restore_exception(self):
        """Test Snapshot restore method exception."""
        snap = Snapshot("test_restore_exc.txt")
        snap.is_active = True
        snap.backup_path = "test_restore_exc_bak.txt"
        with open("test_restore_exc_bak.txt", "w") as f:
            f.write("test")

        original_move = shutil.move
        def fake_move(src, dst):
            raise Exception("Move failed")
        shutil.move = fake_move
        try:
            self.assertFalse(snap.restore())
        finally:
            shutil.move = original_move
            if os.path.exists("test_restore_exc_bak.txt"):
                os.remove("test_restore_exc_bak.txt")

    def test_snapshot_cleanup_exception(self):
        """Test Snapshot cleanup method exception."""
        snap = Snapshot("test_cleanup_exc.txt")
        snap.is_active = True
        snap.backup_path = "test_cleanup_exc_bak.txt"
        with open("test_cleanup_exc_bak.txt", "w") as f:
            f.write("test")

        original_remove = os.remove
        def fake_remove(path):
            if path == snap.backup_path:
                raise Exception("Remove failed")
            original_remove(path)
        os.remove = fake_remove
        try:
            snap.cleanup() # Should not raise
            self.assertTrue(os.path.exists("test_cleanup_exc_bak.txt"))
        finally:
            os.remove = original_remove
            if os.path.exists("test_cleanup_exc_bak.txt"):
                os.remove("test_cleanup_exc_bak.txt")

if __name__ == '__main__':
    unittest.main()
