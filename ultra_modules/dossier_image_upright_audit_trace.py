import os
import tempfile
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from PIL import Image, ExifTags
from docx import Document
from docx.shared import Inches

class AuditLogger:
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def log(self, action: str, details: Dict[str, Any]) -> None:
        self.logs.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        })

    def get_logs(self) -> List[Dict[str, Any]]:
        return self.logs


def _get_file_hash(filepath: str) -> str:
    """Calculate SHA-256 hash of a file."""
    if not os.path.exists(filepath):
        return ""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def _correct_image_orientation(image_path: str, logger: AuditLogger) -> Optional[str]:
    """Correct image orientation based on EXIF data and save to a temp file."""
    try:
        with Image.open(image_path) as img:
            file_hash = _get_file_hash(image_path)

            # Find orientation tag
            orientation_tag = None
            for key, val in ExifTags.TAGS.items():
                if val == 'Orientation':
                    orientation_tag = key
                    break

            exif = img.getexif()
            orientation = exif.get(orientation_tag, 1) if exif and orientation_tag else 1

            if orientation in (3, 6, 8):
                rotated_img = img
                if orientation == 3:
                    rotated_img = img.rotate(180, expand=True)
                    logger.log("exif_correction", {"file": image_path, "hash": file_hash, "action": "rotated 180"})
                elif orientation == 6:
                    rotated_img = img.rotate(270, expand=True)
                    logger.log("exif_correction", {"file": image_path, "hash": file_hash, "action": "rotated 270"})
                else: # orientation == 8
                    rotated_img = img.rotate(90, expand=True)
                    logger.log("exif_correction", {"file": image_path, "hash": file_hash, "action": "rotated 90"})

                # Strip EXIF from saved file to avoid re-rotation
                data = list(rotated_img.getdata())
                image_without_exif = Image.new(rotated_img.mode, rotated_img.size)
                image_without_exif.putdata(data)

                fd, temp_path = tempfile.mkstemp(suffix=".jpg")
                os.close(fd)
                image_without_exif.save(temp_path, "JPEG")
                return temp_path
            else:
                logger.log("exif_correction", {"file": image_path, "hash": file_hash, "action": "no rotation needed"})
                # We need to return a path to a copy or original, but safer to convert to standard format temp file
                fd, temp_path = tempfile.mkstemp(suffix=".jpg")
                os.close(fd)
                # Convert to RGB to safely save as JPEG
                rgb_im = img.convert('RGB')
                rgb_im.save(temp_path, "JPEG")
                return temp_path
    except Exception as e:
        logger.log("exif_correction_error", {"file": image_path, "error": str(e)})
        return None

def process_dossier(image_paths: Optional[List[str]] = None, output_docx_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Process employee dossier images: correct EXIF rotation, deduplicate, and compile into a Word document.

    Args:
        image_paths: List of image file paths. Defaults to empty list if None.
        output_docx_path: Path to save the output Word doc. Defaults to a temp file if None.

    Returns:
        Dict containing:
            - 'status': 'success' or 'error'
            - 'output_path': Path to the generated Word document (if successful)
            - 'audit_logs': Background logs tracing the entire process
            - 'processed_count': Number of successfully processed images
            - 'deduplicated_count': Number of duplicated images skipped
    """
    logger = AuditLogger()

    # Missing parameter defaults
    if image_paths is None:
        image_paths = []

    if output_docx_path is None:
        fd, output_docx_path = tempfile.mkstemp(suffix=".docx")
        os.close(fd)
        logger.log("default_parameter_applied", {"parameter": "output_docx_path", "value": output_docx_path})

    logger.log("process_start", {"input_count": len(image_paths), "output_path": output_docx_path})

    processed_images = []
    seen_hashes = set()
    deduplicated_count = 0
    temp_files_to_cleanup = []

    try:
        # 1. Deduplication and EXIF correction
        for path in image_paths:
            if not isinstance(path, str):
                logger.log("dirty_data_skipped", {"reason": "path is not a string", "value": str(path)})
                continue

            if not os.path.exists(path):
                logger.log("dirty_data_skipped", {"reason": "file not found", "path": path})
                continue

            file_hash = _get_file_hash(path)
            if file_hash in seen_hashes:
                deduplicated_count += 1
                logger.log("deduplication", {"path": path, "hash": file_hash, "action": "skipped"})
                continue

            seen_hashes.add(file_hash)

            corrected_path = _correct_image_orientation(path, logger)
            if corrected_path:
                processed_images.append(corrected_path)
                temp_files_to_cleanup.append(corrected_path)

        # 2. Word document generation
        doc = Document()
        doc.add_heading('Employee Dossier Images', 0)

        for img_path in processed_images:
            try:
                doc.add_picture(img_path, width=Inches(6.0))
                doc.add_paragraph() # Add some spacing
                logger.log("word_compilation", {"action": "added_image", "temp_path": img_path})
            except Exception as e:
                logger.log("word_compilation_error", {"temp_path": img_path, "error": str(e)})

        doc.save(output_docx_path)
        logger.log("process_complete", {"processed_count": len(processed_images), "output_path": output_docx_path})

        return {
            "status": "success",
            "output_path": output_docx_path,
            "audit_logs": logger.get_logs(),
            "processed_count": len(processed_images),
            "deduplicated_count": deduplicated_count
        }

    except Exception as e:
        logger.log("fatal_error", {"error": str(e)})
        return {
            "status": "error",
            "output_path": None,
            "audit_logs": logger.get_logs(),
            "processed_count": len(processed_images),
            "deduplicated_count": deduplicated_count
        }
    finally:
        # Cleanup temporary files
        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.log("cleanup_error", {"temp_path": temp_file, "error": str(e)})
