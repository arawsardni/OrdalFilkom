"""Source citation display components"""
import os
from typing import List, Dict
import streamlit as st

from src.utils.pdf_renderer import render_pdf_page
from src.config.settings import Settings


def display_sources(sources_data: List[Dict]):
    """
    Display source citations with PDF preview
    
    Args:
        sources_data: List of source dicts with file_name, page, category, score
    """
    if not sources_data:
        return
    
    st.markdown("---")
    st.markdown("### 📚 Sumber Referensi")
    
    for idx, source_info in enumerate(sources_data, 1):
        _display_source_card(idx, source_info, len(sources_data))


def _display_source_card(idx: int, source_info: Dict, total_sources: int):
    """
    Display single source card with file info and PDF preview
    
    Args:
        idx: Source index (1-based)
        source_info: Dict with file_name, page, category, score
        total_sources: Total number of sources (for divider logic)
    """
    with st.container():
        # Header with file info and relevance score
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"**{idx}. {source_info['file_name']}**")
            st.caption(f"📄 Halaman {source_info['page']} • 📁 {source_info['category']}")
        
        with col2:
            st.metric("Relevansi", source_info['score'], label_visibility="collapsed")
        
        # PDF preview
        _display_pdf_preview(source_info)
        
        # Divider between sources (but not after last one)
        if idx < total_sources:
            st.divider()


def _display_pdf_preview(source_info: Dict):
    """
    Display PDF page preview in expander
    
    Args:
        source_info: Dict with file_name, page, category
    """
    with st.expander("👁️ Lihat halaman PDF"):
        pdf_path = os.path.join(
            Settings.DATASET_DIR, 
            source_info['category'], 
            source_info['file_name']
        )
        
        if not os.path.exists(pdf_path):
            st.warning(f"File tidak ditemukan: {pdf_path}")
            return
        
        try:
            # Convert page label to 0-indexed page number
            page_num = int(source_info['page']) - 1 if source_info['page'] != 'Unknown' else 0
            
            # Render PDF page as image
            img = render_pdf_page(pdf_path, page_num, dpi=Settings.PDF_RENDER_DPI)
            
            if img:
                st.image(
                    img, 
                    caption=f"Halaman {source_info['page']} dari {source_info['file_name']}", 
                    use_column_width=True
                )
            else:
                st.warning("Gagal merender halaman PDF")
                
        except Exception as e:
            st.error(f"Error menampilkan PDF: {e}")
