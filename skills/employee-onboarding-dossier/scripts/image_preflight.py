import os
import pymupdf
from PIL import Image, ImageOps

def process_image(img_path, work_dir, idx, rotate=0):
    """
    Reads the image using Pillow, auto-corrects EXIF orientation,
    applies any explicit rotation, and saves to work_dir.
    Returns the new file name, full path, width, and height.
    """
    ext = os.path.splitext(img_path)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg']:
        ext = '.png'
    out_name = f"image{idx}{ext}"
    out_path = os.path.join(work_dir, out_name)

    with Image.open(img_path) as img:
        # Auto-rotate based on EXIF
        img = ImageOps.exif_transpose(img)

        # Apply custom rotation if any
        if rotate:
            # Pillow uses counter-clockwise rotation, while the old sips used clockwise
            # To be compatible, if we assume 'rotate' is clockwise degrees, we do:
            img = img.rotate(-rotate, expand=True)

        # For PNG images we need to preserve transparency or flatten to a white background
        # Ensure it's in a compatible mode before saving, especially if converting format
        if img.mode in ('RGBA', 'P') and ext in ['.jpg', '.jpeg']:
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else img.convert('RGBA').split()[3])
            img = bg

        img.save(out_path)
        w, h = img.size

    return out_name, out_path, w, h

def render_pdf(pdf_path, temp_dir, scale=2.0):
    """
    Uses PyMuPDF to render each page of a PDF as a PNG image.
    Returns a sorted list of the generated image paths.
    """
    out_sub = os.path.join(temp_dir, os.path.basename(pdf_path) + "_pages")
    os.makedirs(out_sub, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    mat = pymupdf.Matrix(scale, scale)

    pages = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=mat)
        out_path = os.path.join(out_sub, f"page_{page_num+1:03d}.png")
        pix.save(out_path)
        pages.append(out_path)

    doc.close()
    return sorted(pages)
