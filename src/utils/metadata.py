import os
import re


def get_meta(file_path: str) -> dict:
    """
    Extracts metadata from the filename and path.
    
    Expected filename format: YYYY_Kategori_JudulSingkat.pdf
    
    Args:
        file_path: Full or relative path to the document file
    
    Returns:
        dict: Metadata containing:
            - file_name: Original file name
            - year: Extracted year (first 4 digits) or 2024 as fallback
            - category: Parent folder name
    """
    file_name = os.path.basename(file_path)
    parent_folder = os.path.basename(os.path.dirname(file_path))
    
    # Extract year using regex
    year_match = re.match(r"^(\d{4})_", file_name)
    year = int(year_match.group(1)) if year_match else 2024
    
    return {
        "file_name": file_name,
        "year": year,
        "category": parent_folder
    }
