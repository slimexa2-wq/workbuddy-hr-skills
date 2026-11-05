import os
import io
import time
from typing import List, Union
from PIL import Image, ExifTags
from docx import Document
from docx.shared import Inches

def fix_image_rotation(img: Image.Image) -> Image.Image:
    """
    Safely reads EXIF orientation and corrects image rotation.
    Silent fallback and return original image on failure.
    """
    try:
        if hasattr(img, '_getexif') and img._getexif() is not None:
            exif = img._getexif()
            orientation_key = None
            for key, val in ExifTags.TAGS.items():
                if val == 'Orientation':
                    orientation_key = key
                    break

            if orientation_key and orientation_key in exif:
                orientation = exif[orientation_key]
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
    except Exception:
        pass
    return img

def create_upright_dossier_word(image_sources: Union[List[Union[str, bytes]], None] = None, output_path: str = None) -> Union[str, None]:
    """
    Accepts a list of image paths/bytes, gracefully falls back to default values if parameters are missing,
    normalizes images, corrects EXIF orientation, and inserts them nicely into a Word document.
    """
    if image_sources is None:
        image_sources = []

    if output_path is None:
        # Default output path
        output_path = f"dossier_output_{int(time.time() * 1000)}.docx"

    doc = Document()
    added_images = False

    for source in image_sources:
        try:
            img = None
            if isinstance(source, str):
                if os.path.isfile(source):
                    img = Image.open(source)
            elif isinstance(source, bytes):
                img = Image.open(io.BytesIO(source))

            if img:
                img = fix_image_rotation(img)
                # Normalize to RGB if necessary for saving to jpeg to insert in word
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Save to a temporary bytes buffer to insert into Word
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=95)
                img_byte_arr.seek(0)

                doc.add_picture(img_byte_arr, width=Inches(6)) # Default width, fits A4 nicely
                added_images = True

        except Exception:
            # Silently ignore invalid data (corrupted bytes, random strings, etc.)
            continue

    try:
        # We save even if there's no valid image, just an empty doc
        doc.save(output_path)
        return output_path
    except Exception:
        return None
