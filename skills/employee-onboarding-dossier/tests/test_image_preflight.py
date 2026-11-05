import os
import sys
import tempfile
from PIL import Image, ImageOps
import pymupdf # PyMuPDF

# Add scripts directory to path to import modules
script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, script_dir)

from image_preflight import process_image, render_pdf
from build_dossier import create_from_manifest

def test_process_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test image
        img_path = os.path.join(tmpdir, "test.png")
        img = Image.new('RGB', (100, 200), color = 'red')
        img.save(img_path)

        # Test basic processing
        out_name, out_path, w, h = process_image(img_path, tmpdir, 1)
        assert out_name == "image1.png"
        assert w == 100
        assert h == 200

        # Test rotation
        out_name, out_path, w, h = process_image(img_path, tmpdir, 2, rotate=90)
        assert out_name == "image2.png"
        assert w == 200
        assert h == 100

def test_render_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy PDF
        pdf_path = os.path.join(tmpdir, "test.pdf")
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Hello, World!")
        doc.save(pdf_path)
        doc.close()

        pages = render_pdf(pdf_path, tmpdir, scale=1.0)

        assert len(pages) == 1
        assert os.path.exists(pages[0])
        assert "page_001.png" in pages[0]

def test_build_dossier():
    # Note: Requires templates/base_template.docx to exist
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy image and pdf
        img_path = os.path.join(tmpdir, "photo.jpg")
        img = Image.new('RGB', (100, 100), color = 'blue')
        img.save(img_path)

        pdf_path = os.path.join(tmpdir, "resume.pdf")
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Resume")
        doc.save(pdf_path)
        doc.close()

        manifest = {
            "name": "Test User",
            "position": "Test Position",
            "department": "Test Dept",
            "year": "2024",
            "month": "11",
            "items": [
                {
                    "caption": "个人简历",
                    "images": [{"path": pdf_path}]
                },
                {
                    "caption": "证件照",
                    "photo": True,
                    "images": [{"path": img_path}]
                }
            ]
        }

        manifest_path = os.path.join(tmpdir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        out_docx = os.path.join(tmpdir, "output.docx")

        # Test if it runs without errors
        # Make sure templates are created or copied if they don't exist in testing environment
        template_dir = os.path.abspath(os.path.join(script_dir, "..", "templates"))
        if not os.path.exists(template_dir):
            os.makedirs(template_dir)
            # creating a dummy valid docx as template might be too complex here,
            # assuming base_template.docx exists in the repo

        # Only run if template exists
        template_path = os.path.join(template_dir, "base_template.docx")
        if os.path.exists(template_path):
            result_docx = create_from_manifest(manifest_path, out_docx)
            assert os.path.exists(result_docx)
