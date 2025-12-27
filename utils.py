import os
import re
import fitz  # PyMuPDF
from PIL import Image
import io

def get_meta(file_path: str) -> dict:
    """
    Extracts metadata from the filename and path.
    Format: YYYY_Kategori_JudulSingkat.pdf
    
    Metadata extracted:
    - file_name: Original file name
    - year: Year (first 4 digits)
    - category: Parent folder name
    """
    file_name = os.path.basename(file_path)
    parent_folder = os.path.basename(os.path.dirname(file_path))
    
    # Extract year using regex (looking for 4 digits at the start)
    year_match = re.match(r"^(\d{4})_", file_name)
    year = int(year_match.group(1)) if year_match else 2024 # Default fallback? Or handle error?
    
    return {
        "file_name": file_name,
        "year": year,
        "category": parent_folder
    }

def render_pdf_page(pdf_path: str, page_number: int, dpi: int = 150) -> Image.Image:
    """
    Render a specific page from PDF to PIL Image.
    
    Args:
        pdf_path: Full path to PDF file
        page_number: Page number (0-indexed)
        dpi: Resolution for rendering (default 150 for good quality)
    
    Returns:
        PIL Image object of the rendered page
    """
    try:
        # Open PDF
        doc = fitz.open(pdf_path)
        
        # Ensure page number is valid
        if page_number < 0 or page_number >= len(doc):
            page_number = 0  # Fallback to first page
        
        # Get the page
        page = doc[page_number]
        
        # Render page to image (zoom factor = dpi/72)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        doc.close()
        return img
        
    except Exception as e:
        print(f"Error rendering PDF page: {e}")
        return None
