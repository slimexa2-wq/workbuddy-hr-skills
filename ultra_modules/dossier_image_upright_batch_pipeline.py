import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import List, Dict, Any, Optional

from PIL import Image, ExifTags
from docx import Document
from docx.shared import Inches

logger = logging.getLogger(__name__)

def setup_logger():
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

setup_logger()

def correct_image_orientation(image: Image.Image) -> Image.Image:
    """
    Corrects image orientation based on EXIF data.
    If the image lacks EXIF or the EXIF is corrupt, it falls back gracefully and returns the original image.
    """
    try:
        if hasattr(image, '_getexif'):
            exif = image._getexif()
            if exif:
                orientation_key = None
                for key, val in ExifTags.TAGS.items():
                    if val == 'Orientation':
                        orientation_key = key
                        break

                if orientation_key and orientation_key in exif:
                    orientation = exif[orientation_key]
                    if orientation == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation == 8:
                        image = image.rotate(90, expand=True)
    except Exception as e:
        logger.warning(f"Failed to process EXIF orientation, falling back to original image. Error: {e}")
    return image

def process_single_record(record: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Processes a single dossier record containing image path.
    Extracts image, corrects rotation, and embeds it into a Word document.
    """
    record_id = record.get('id', 'unknown')
    image_path = record.get('image_path')

    result = {
        'id': record_id,
        'status': 'failed',
        'output_path': None,
        'error': None
    }

    if not image_path:
        result['error'] = "Missing image_path"
        return result

    if not os.path.exists(image_path):
        result['error'] = f"Image file not found: {image_path}"
        return result

    try:
        # Load and correct image
        with Image.open(image_path) as img:
            img = correct_image_orientation(img)

            # Convert to RGB if needed (e.g. RGBA to RGB for saving/docx)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # Save temporarily to BytesIO to insert into docx
            img_io = BytesIO()
            img.save(img_io, format='JPEG', quality=95)
            img_io.seek(0)

        # Create Word document
        doc = Document()
        doc.add_heading(f'Dossier: {record_id}', 0)

        # Calculate image width to fit page, default A4 width is ~6 inches
        doc.add_picture(img_io, width=Inches(6.0))

        # Save output
        output_filename = f"dossier_{record_id}.docx"
        output_path = os.path.join(output_dir, output_filename)
        doc.save(output_path)

        result['status'] = 'success'
        result['output_path'] = output_path

    except Exception as e:
        logger.error(f"Error processing record {record_id}: {e}")
        result['error'] = str(e)

    return result

def process_dossier_batch(records: List[Dict[str, Any]], output_dir: str, max_workers: int = 10) -> Dict[str, Any]:
    """
    Processes a batch of dossier records concurrently.
    Provides high throughput stream processing with zero blocking result aggregation.
    Defaults to 10 workers for sensible concurrency without extreme overhead.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    results = []
    success_count = 0
    failed_count = 0

    if not records:
        logger.warning("Empty records batch provided.")
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'results': results
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_record = {
            executor.submit(process_single_record, record, output_dir): record
            for record in records
        }

        for future in as_completed(future_to_record):
            record = future_to_record[future]
            try:
                res = future.result()
                results.append(res)
                if res['status'] == 'success':
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as exc:
                record_id = record.get('id', 'unknown')
                logger.error(f"Record {record_id} generated an exception: {exc}")
                results.append({
                    'id': record_id,
                    'status': 'failed',
                    'output_path': None,
                    'error': str(exc)
                })
                failed_count += 1

    return {
        'total': len(records),
        'success': success_count,
        'failed': failed_count,
        'results': results
    }
