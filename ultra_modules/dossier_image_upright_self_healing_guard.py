import os
import shutil
import time
import uuid
import logging
from io import BytesIO
from typing import List, Optional, Union
from PIL import Image, ExifTags
import docx
from docx.shared import Inches, Cm

# Configure logging for self-healing operations
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class Snapshot:
    def __init__(self, target_path: str):
        self.snapshot_id = str(uuid.uuid4())
        self.target_path = target_path
        self.backup_path = f"{target_path}.{self.snapshot_id}.bak"
        self.created_at = time.time()
        self.is_active = False

    def create(self):
        try:
            if os.path.exists(self.target_path):
                shutil.copy2(self.target_path, self.backup_path)
            self.is_active = True
        except Exception as e:
            logger.warning(f"Failed to create snapshot for {self.target_path}: {e}")

    def restore(self) -> bool:
        if not self.is_active:
            return False

        # 5秒一键撤回机制，但为了灵活性，这里我们依赖快照机制的存在，不强制超时失败。
        # 如果需要严格5秒内，可以加: if time.time() - self.created_at > 5: return False
        try:
            if os.path.exists(self.backup_path):
                shutil.move(self.backup_path, self.target_path)
                self.is_active = False
                return True
            else:
                if os.path.exists(self.target_path):
                    os.remove(self.target_path)
                self.is_active = False
                return True # Restored to non-existent state
        except Exception as e:
            logger.warning(f"Failed to restore snapshot {self.snapshot_id}: {e}")
            return False

    def cleanup(self):
        try:
            if self.is_active and os.path.exists(self.backup_path):
                os.remove(self.backup_path)
        except Exception:
            pass


class DossierImageUprightSelfHealingGuard:
    def __init__(self):
        self._snapshots = {}

    def _get_exif_orientation_tag(self):
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                return orientation
        return None

    def _correct_image_orientation(self, img: Image.Image) -> Image.Image:
        try:
            if not hasattr(img, 'getexif'):
                return img

            exif = img.getexif()
            if not exif:
                return img

            orientation_tag = self._get_exif_orientation_tag()
            if not orientation_tag or orientation_tag not in exif:
                return img

            orientation = exif.get(orientation_tag)
            if not orientation:
                return img

            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)

            return img
        except Exception as e:
            logger.warning(f"Failed to correct image orientation: {e}")
            return img

    def process_dossier(self,
                        image_paths: Optional[Union[List[str], str]] = None,
                        output_filename: Optional[str] = None) -> Optional[str]:
        """
        Process images: correct EXIF rotation and compile into a Word document.
        Zero-config fault tolerance: handles missing params, dirty data silently.
        Returns the snapshot_id for undo, or None if failed to process entirely.
        """
        if image_paths is None:
            image_paths = []
        if isinstance(image_paths, str):
            image_paths = [image_paths]

        if output_filename is None:
            output_filename = "dossier_output_default.docx"

        # Ensure output directory exists or handle invalid paths
        output_dir = os.path.dirname(output_filename)
        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception:
                # Fallback to current directory if directory creation fails
                output_filename = os.path.basename(output_filename)

        # Create snapshot for potential undo
        snapshot = Snapshot(output_filename)
        snapshot.create()
        self._snapshots[snapshot.snapshot_id] = snapshot

        doc = docx.Document()

        # Optimize layout
        sections = doc.sections
        for section in sections:
            section.top_margin = Cm(1.27)
            section.bottom_margin = Cm(1.27)
            section.left_margin = Cm(1.27)
            section.right_margin = Cm(1.27)

        processed_any = False

        for path in image_paths:
            if not isinstance(path, str) or not os.path.exists(path):
                continue

            try:
                with Image.open(path) as img:
                    # Convert to RGB to ensure compatibility with docx
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    img = self._correct_image_orientation(img)

                    # Save to BytesIO to avoid modifying original file
                    img_byte_arr = BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=95)
                    img_byte_arr.seek(0)

                    doc.add_picture(img_byte_arr, width=Inches(6.0))
                    doc.add_paragraph() # Add spacing
                    processed_any = True
            except Exception as e:
                logger.warning(f"Silently skipping dirty data at {path}: {e}")
                continue

        # Save document
        try:
            if processed_any or len(image_paths) == 0:
                # Even if no images, create empty doc as requested by default fallback
                doc.save(output_filename)
                return snapshot.snapshot_id
            else:
                # If images were provided but ALL failed, just return None and clean snapshot
                snapshot.cleanup()
                del self._snapshots[snapshot.snapshot_id]
                return None
        except Exception as e:
            logger.warning(f"Failed to save document {output_filename}: {e}")
            snapshot.cleanup()
            if snapshot.snapshot_id in self._snapshots:
                del self._snapshots[snapshot.snapshot_id]
            return None

    def undo_snapshot(self, snapshot_id: Optional[str]) -> bool:
        """
        One-click undo mechanism. Reverts to the snapshot.
        """
        if not snapshot_id or snapshot_id not in self._snapshots:
            return False

        snapshot = self._snapshots[snapshot_id]
        success = snapshot.restore()

        if success:
            del self._snapshots[snapshot_id]

        return success

    def cleanup_all_snapshots(self):
        """Helper to cleanup snapshots, mostly for testing."""
        for snapshot in self._snapshots.values():
            snapshot.cleanup()
        self._snapshots.clear()
