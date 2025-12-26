import os
import re

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
