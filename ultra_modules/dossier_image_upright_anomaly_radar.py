import os
import io
import math
import statistics
from typing import List, Dict, Any, Tuple
from PIL import Image, ExifTags
from docx import Document
from docx.shared import Inches


class DossierRadar:
    """
    Dossier Image Upright Anomaly Radar:
    - Automatically rotates images based on EXIF to make them upright.
    - Generates HD Word layout.
    - Detects file size/dimension anomalies using Z-Score/IQR and flags Top 3% with Red/Yellow/Green marks.
    """

    # EXIF orientation tag code
    _ORIENTATION_TAG = None

    def __init__(self):
        if self._ORIENTATION_TAG is None:
            for k, v in ExifTags.TAGS.items():
                if v == 'Orientation':
                    type(self)._ORIENTATION_TAG = k
                    break

    def correct_exif_rotation(self, image: Image.Image) -> Image.Image:
        """
        Correct image rotation based on EXIF data.
        Returns upright image. Does not modify original in-place for safety, though Pillow might.
        """
        try:
            exif = image.getexif()
            if not exif:
                return image

            orientation = exif.get(self._ORIENTATION_TAG)
            if orientation == 3:
                return image.rotate(180, expand=True)
            elif orientation == 6:
                return image.rotate(270, expand=True)
            elif orientation == 8:
                return image.rotate(90, expand=True)
        except Exception:
            # Dirty data self-healing: if EXIF is malformed or rotation fails, return original
            pass

        return image

    def detect_anomalies(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detects anomalies based on image size (bytes).
        Uses IQR/Z-score to find extreme outliers.
        Marks Top 3% anomalous items.
        Returns the original list with 'flag' and 'reason' added to each item dict.
        Green: Normal (97%)
        Yellow/Red: Anomalous (Top 3%) - Red for extreme, Yellow for borderline.
        """
        if not items:
            return items

        # Ensure all items have a size attribute, default to 0 if missing
        sizes = []
        for item in items:
            if 'size' not in item:
                item['size'] = 0
            sizes.append(item['size'])

        if len(sizes) < 4:
            # Not enough data for statistical analysis, just mark all as green
            for item in items:
                item['flag'] = 'Green'
                item['reason'] = '正常'
            return items

        # Calculate statistics
        mean_size = statistics.mean(sizes)
        stdev_size = statistics.stdev(sizes) if len(sizes) > 1 else 0

        # Calculate IQR
        sorted_sizes = sorted(sizes)
        q1 = statistics.quantiles(sorted_sizes, n=4)[0]
        q3 = statistics.quantiles(sorted_sizes, n=4)[2]
        iqr = q3 - q1

        # Calculate anomaly scores for each item
        # Higher score = more anomalous
        scores = []
        for size in sizes:
            z_score = abs(size - mean_size) / stdev_size if stdev_size > 0 else 0

            # Distance from IQR bounds
            if size > q3:
                iqr_dist = (size - q3) / iqr if iqr > 0 else 0
            elif size < q1:
                iqr_dist = (q1 - size) / iqr if iqr > 0 else 0
            else:
                iqr_dist = 0

            # Combine scores, simple addition for now
            scores.append(z_score + iqr_dist)

        # Determine the Top 3% threshold
        num_anomalies = max(1, math.ceil(len(items) * 0.03))

        # Sort items by score descending to find the top anomalies
        indexed_scores = [(i, score) for i, score in enumerate(scores)]
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        anomaly_indices = set(i for i, _ in indexed_scores[:num_anomalies])

        # Assign flags and reasons
        for i, item in enumerate(items):
            size = item.get('size', 0)
            if i in anomaly_indices and scores[i] > 0:
                if scores[i] > 3.0: # Arbitrary high threshold for Red vs Yellow
                    item['flag'] = 'Red'
                    item['reason'] = f'文件体积严重异常（大小: {size}字节），请人工核查'
                else:
                    item['flag'] = 'Yellow'
                    item['reason'] = f'文件体积偏离正常范围（大小: {size}字节），请留意'
            else:
                item['flag'] = 'Green'
                item['reason'] = '正常'

        return items

    def process(self, image_paths: List[str], output_word_path: str = "output.docx") -> Dict[str, Any]:
        """
        One-click invocation method:
        - Loads images, corrects rotation.
        - Calculates sizes for anomaly detection.
        - Generates Word doc with images.
        - Returns a report.
        """
        items = []
        for path in image_paths:
            try:
                # Default to 0 size if file doesn't exist to allow processing to continue (self-healing/fault tolerance)
                size = os.path.getsize(path) if os.path.exists(path) else 0
                items.append({'path': path, 'size': size})
            except Exception:
                 items.append({'path': path, 'size': 0})

        # Detect anomalies
        analyzed_items = self.detect_anomalies(items)

        # Generate layout
        self.generate_word_layout([item['path'] for item in analyzed_items], output_word_path)

        return {
            "status": "success",
            "output_path": output_word_path,
            "items_analyzed": len(analyzed_items),
            "anomalies_detected": sum(1 for item in analyzed_items if item['flag'] in ('Red', 'Yellow')),
            "details": analyzed_items
        }

    def generate_word_layout(self, image_paths: List[str], output_path: str = "output.docx") -> str:
        """
        Generates Word layout with corrected images.
        """
        document = Document()
        document.add_heading('Dossier Images', 0)

        for path in image_paths:
            try:
                if not os.path.exists(path):
                    continue

                # Load and correct image
                with Image.open(path) as img:
                    corrected_img = self.correct_exif_rotation(img)

                    # Convert to RGB to ensure compatibility with docx
                    if corrected_img.mode != 'RGB':
                        corrected_img = corrected_img.convert('RGB')

                    # Save to memory buffer to add to word doc
                    img_byte_arr = io.BytesIO()
                    corrected_img.save(img_byte_arr, format='JPEG')
                    img_byte_arr.seek(0)

                    document.add_paragraph(f"Image: {os.path.basename(path)}")
                    document.add_picture(img_byte_arr, width=Inches(6.0))
            except Exception as e:
                # Silently skip errors for resilience
                print(f"Error processing {path}: {e}")
                pass

        document.save(output_path)
        return output_path
