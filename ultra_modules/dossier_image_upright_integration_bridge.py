import os
import io
from typing import Dict, Any, List, Optional
from PIL import Image, ImageOps
from docx import Document
from docx.shared import Inches

class DossierImageUprightIntegrationBridge:
    """
    Cross-system data contract bridge for dossier image upright and word layout.
    Automatically detects schema version differences (e.g., v1 flat, v2 nested, custom vendor formats)
    and silently maps them without manual configuration.
    It then processes the images (EXIF rotation) and places them into a Word document.
    """

    @classmethod
    def process_payload(cls, payload: Any) -> Optional[str]:
        # 1. Parameter fallback & dirty data auto-healing
        if not isinstance(payload, dict):
            # Fallback for extreme boundary cases (e.g., just passing a string or list directly)
            if isinstance(payload, str):
                return cls._process_images_to_word(image_paths=[payload], output_docx_path=None)
            if isinstance(payload, list):
                return cls._process_images_to_word(image_paths=payload, output_docx_path=None)
            # Total garbage data fallback
            return cls._process_images_to_word(image_paths=[], output_docx_path=None)

        image_paths: List[str] = []
        output_docx_path: Optional[str] = None

        # 2. Schema auto-detection and silent mapping via recursive discovery
        def extract_fields(data: Dict[Any, Any]) -> None:
            nonlocal output_docx_path
            for key, value in data.items():
                if isinstance(value, dict):
                    extract_fields(value)
                elif isinstance(value, list):
                    # Autodetect lists of image paths
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            image_paths.append(item.strip())
                elif isinstance(value, str) and value.strip():
                    val_str = value.strip()
                    lower_key = str(key).lower()

                    # Heuristic for output docx path
                    if val_str.endswith('.docx'):
                        if not output_docx_path:
                            output_docx_path = val_str
                    elif 'out' in lower_key or 'export' in lower_key or 'doc' in lower_key:
                        if not output_docx_path and val_str.endswith('.docx'):
                            output_docx_path = val_str

                    # Heuristic for single image paths in odd fields
                    elif val_str.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        image_paths.append(val_str)

        extract_fields(payload)

        # Deduplicate while preserving order
        seen = set()
        clean_image_paths = []
        for p in image_paths:
            if p not in seen:
                seen.add(p)
                clean_image_paths.append(p)

        # 3. Call core engine implementation with cleanly mapped data
        return cls._process_images_to_word(
            image_paths=clean_image_paths,
            output_docx_path=output_docx_path
        )

    @classmethod
    def _process_images_to_word(cls, image_paths: List[str], output_docx_path: Optional[str]) -> Optional[str]:
        """
        Process dossier images, applying EXIF rotation to make them upright,
        and inserting them into a Word document.
        """
        if not isinstance(output_docx_path, str) or not output_docx_path.strip():
            output_docx_path = "output_dossier.docx"

        document = Document()

        # Dirty data cleaning for paths
        valid_paths = []
        for path in image_paths:
            if isinstance(path, str) and path.strip():
                valid_paths.append(path.strip())

        # Core EXIF upright and docx algorithm
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

        # Save with directory fallback
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
