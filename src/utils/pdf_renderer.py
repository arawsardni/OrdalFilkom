import fitz  # PyMuPDF
from PIL import Image
import io
from typing import Optional


def render_pdf_page(pdf_path: str, page_number: int, dpi: int = 150) -> Optional[Image.Image]:
    """
    Render a specific page from PDF to PIL Image.
    
    Args:
        pdf_path: Full path to PDF file
        page_number: Page number (0-indexed)
        dpi: Resolution for rendering (default 150 for good quality)
            Higher DPI = better quality but slower rendering
    
    Returns:
        PIL Image object of the rendered page, or None if error occurs
    """
    try:
        # Open PDF document
        doc = fitz.open(pdf_path)
        
        # Validate and clamp page number
        if page_number < 0 or page_number >= len(doc):
            page_number = 0  # Fallback to first page
        
        # Get the specified page
        page = doc[page_number]
        
        # Calculate zoom factor from DPI (72 DPI is base)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        # Render page to pixmap (raster image)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert pixmap to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Clean up
        doc.close()
        
        return img
        
    except Exception as e:
        print(f"Error rendering PDF page: {e}")
        return None
