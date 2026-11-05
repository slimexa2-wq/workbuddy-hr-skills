import io
import json
import logging
from typing import Optional, Dict, Any, Union
from PIL import Image, ExifTags
from docx import Document
from docx.shared import Inches

logger = logging.getLogger(__name__)

def process_dossier(
    image_data: Optional[bytes] = None,
    output_format: str = "json",
    title: str = "新员工入职资料处理报告",
    embed_in_word: bool = False
) -> Union[str, Dict[str, Any], bytes]:
    """
    Process employee dossier images (ID cards/diplomas), auto-correct EXIF rotation,
    optionally embed into Word, and generate an explainer card in JSON, HTML, or Markdown.

    Zero-config fault tolerance: defaults are applied, missing/dirty data is cleaned silently.

    Args:
        image_data: Raw bytes of the image
        output_format: "json", "html", or "md"
        title: Title of the output report
        embed_in_word: If True, returns Word document bytes instead of the explainer card string

    Returns:
        Formatted string (HTML/MD), JSON dict, or Word document bytes.
    """
    if output_format not in ("json", "html", "md"):
        output_format = "json"  # default fallback

    if not isinstance(title, str) or not title.strip():
        title = "新员工入职资料处理报告"

    success = False
    message = "未提供图片数据"
    corrected_image_bytes = None
    width, height = 0, 0
    rotated = False

    if image_data:
        try:
            # Handle empty/invalid bytes safely
            image = Image.open(io.BytesIO(image_data))

            # Auto-rotate based on EXIF
            try:
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break

                exif = image._getexif()
                if exif is not None and orientation in exif:
                    if exif[orientation] == 3:
                        image = image.rotate(180, expand=True)
                        rotated = True
                    elif exif[orientation] == 6:
                        image = image.rotate(270, expand=True)
                        rotated = True
                    elif exif[orientation] == 8:
                        image = image.rotate(90, expand=True)
                        rotated = True
            except (AttributeError, KeyError, IndexError, Exception):
                pass  # Silently ignore EXIF reading errors

            # Ensure it's in a format we can save back
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')

            width, height = image.size
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            corrected_image_bytes = img_byte_arr.getvalue()
            success = True
            message = "图片处理成功（自动正立）" if rotated else "图片处理成功"

        except Exception as e:
            success = False
            message = f"图片处理失败，可能格式不支持或数据损坏。内部错误：{str(e)}"

    # Generate Explainer Data
    explainer_data = {
        "title": title,
        "status": "success" if success else "error",
        "message": message,
        "details": {
            "rotated": rotated,
            "final_width": width,
            "final_height": height
        }
    }

    if embed_in_word and success and corrected_image_bytes:
        try:
            doc = Document()
            doc.add_heading(title, 0)
            doc.add_paragraph(message)
            doc.add_paragraph(f"图像尺寸：{width} x {height}")

            # Add image
            img_stream = io.BytesIO(corrected_image_bytes)
            doc.add_picture(img_stream, width=Inches(6.0))

            doc_byte_arr = io.BytesIO()
            doc.save(doc_byte_arr)
            return doc_byte_arr.getvalue()
        except Exception as e:
            logger.warning(f"Word embedding failed: {e}")
            # Silently fallback to string/dict return

    if output_format == "html":
        color = "green" if success else "red"
        html = f"""
        <div class="dossier-card" style="border: 1px solid #ccc; padding: 16px; border-radius: 8px; font-family: sans-serif;">
            <h2>{explainer_data['title']}</h2>
            <p><strong>状态:</strong> <span style="color: {color};">{explainer_data['status']}</span></p>
            <p><strong>结论:</strong> {explainer_data['message']}</p>
            <ul>
                <li>纠正旋转: {"是" if rotated else "否"}</li>
                <li>尺寸: {width} x {height}</li>
            </ul>
        </div>
        """
        return html.strip()

    elif output_format == "md":
        md = f"""
# {explainer_data['title']}

- **状态**: {explainer_data['status']}
- **结论**: {explainer_data['message']}

**详情**:
- 纠正旋转: {"是" if rotated else "否"}
- 尺寸: {width} x {height}
        """
        return md.strip()

    return explainer_data
