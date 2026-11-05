import os
import io
from PIL import Image, ImageOps
from docx import Document
from docx.shared import Inches

def process_dossier_images_to_word(image_paths=None, output_docx_path=None):
    """
    Process dossier images, applying EXIF rotation to make them upright,
    and inserting them into a Word document. Includes zero-configuration
    auto-healing and dirty data cleaning.
    """
    # 1. Parameter fallback & dirty data auto-healing
    if not isinstance(image_paths, list):
        if isinstance(image_paths, str):
            image_paths = [image_paths]
        else:
            image_paths = []

    if not isinstance(output_docx_path, str) or not output_docx_path.strip():
        output_docx_path = "output_dossier.docx"

    document = Document()

    # 2. Dirty data cleaning
    valid_paths = []
    for path in image_paths:
        if isinstance(path, str) and path.strip():
            valid_paths.append(path.strip())

    # 3. Core algorithm
    for path in valid_paths:
        if not os.path.isfile(path):
            continue

        try:
            with Image.open(path) as img:
                # Fix EXIF orientation using PIL's built-in robust method
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass # Silent failure on EXIF errors

                img_stream = io.BytesIO()
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                img.save(img_stream, format="JPEG")
                img_stream.seek(0)

                document.add_picture(img_stream, width=Inches(6.0))
        except Exception:
            # Silent fallback for unreadable/corrupt images
            continue

    # 4. Save with directory fallback
    output_dir = os.path.dirname(output_docx_path)
    if output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception:
            # Fallback to current directory if directory creation fails
            output_docx_path = os.path.basename(output_docx_path)

    try:
        document.save(output_docx_path)
    except Exception:
        # Fallback to a safe name in current directory if saving fails
        output_docx_path = "fallback_output_dossier.docx"
        try:
            document.save(output_docx_path)
        except Exception:
            return None # Extreme edge case where we can't save at all

    return output_docx_path
