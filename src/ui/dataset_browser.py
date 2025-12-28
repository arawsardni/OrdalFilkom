"""Dataset browser components for sidebar"""
import os
import fitz
import base64
import streamlit as st
from typing import Dict, List
from src.config.settings import Settings
from src.utils.metadata import get_meta
from src.utils.pdf_renderer import render_pdf_page


def get_dataset_files() -> Dict[str, List[Dict]]:
    """
    Scan dataset directory and organize files by category
    
    Returns:
        Dict with category as key and list of file info dicts as value
    """
    

    dataset_dir = Settings.DATASET_DIR
    files_by_category = {}
    
    if not os.path.exists(dataset_dir):
        return {}
    
    # Iterate through categories (subdirectories)
    for category in sorted(os.listdir(dataset_dir)):
        category_path = os.path.join(dataset_dir, category)
        
        if not os.path.isdir(category_path):
            continue
        
        files_by_category[category] = []
        
        # Get all PDF files in category
        for filename in sorted(os.listdir(category_path)):
            if filename.endswith('.pdf'):
                file_path = os.path.join(category_path, filename)
                
                # Get metadata
                metadata = get_meta(file_path)

                # Get file size
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)
                
                # Get page count
                try:
                    doc = fitz.open(file_path)
                    page_count = len(doc)
                    doc.close()
                except:
                    page_count = 0
                
                files_by_category[category].append({
                    'filename': filename,
                    'path': file_path,
                    'year': metadata.get('year', 'N/A'),
                    'page_count': page_count,
                    'category': category,
                    'size_mb': size_mb
                })
    
    return files_by_category


def render_dataset_browser():
    """Render dataset browser in sidebar with VSCode-style tree structure"""
    
    # Custom CSS to reduce spacing
    st.markdown("""
        <style>
        /* Reduce spacing in sidebar */
        .stSidebar [data-testid="stExpander"] {
            margin-bottom: 0.5rem !important;
        }
        .stSidebar .stMarkdown {
            margin-bottom: 0.1rem !important;
        }
        .stSidebar .stCaption {
            margin-top: -0.3rem !important;
            margin-bottom: 0.3rem !important;
        }
        .stSidebar hr {
            margin-top: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.sidebar.title("📚 Dokumen Aseli")
    st.sidebar.markdown("*nih klo mw lihat dokumen asli akademik FILKOM*")
    st.sidebar.markdown("---")
    
    # Get all files organized by category
    files_by_category = get_dataset_files()
    
    if not files_by_category:
        st.sidebar.warning("Dokumen tidak ditemukan")
        return
    
    # tree view with expanders for each category
    for category, files in files_by_category.items():
        with st.sidebar.expander(f"📁 {category.replace('_', ' ').title()[2:]}", expanded=False):            
            # List files in this category
            for idx, file_info in enumerate(files):
                file_name = file_info['filename'].replace('.pdf', '')
                file_name = file_name[4:].replace('_', ' ')
                
                # Truncate nama file jika terlalu panjang
                display_name = file_name if len(file_name) <= 45 else file_name[:42] + "..."
                
                # Clickable title button (full width)
                if st.button(
                    f"📄 {display_name}",
                    key=f"view_{category}_{idx}",
                    help=f"Lihat {file_info['filename']}",
                    use_container_width=True
                ):
                    st.session_state['selected_pdf'] = file_info
                
                # File metadata (compact)
                st.caption(f"📅 {file_info['year']} • 📄 {file_info['page_count']} halaman")
                
                # Divider except for last file
                if idx < len(files) - 1:
                    st.markdown("---")
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Sumber: ")
    st.sidebar.caption("https://filkom.ub.ac.id/profil/dokumen-resmi/")
    st.sidebar.caption("https://filkom.ub.ac.id/apps/")


@st.dialog("📄 PDF Viewer", width="medium")
def show_pdf_viewer():
    """Modal dialog with native browser PDF viewer"""
    if 'selected_pdf' not in st.session_state or not st.session_state['selected_pdf']:
        st.warning("No PDF selected")
        return
    
    file_info = st.session_state['selected_pdf']
    pdf_path = file_info['path']
    filename = file_info['filename']
    file_name = file_info['filename'].replace('.pdf', '')
    file_name = file_name[4:].replace('_', ' ')
    display_name = file_name if len(file_name) <= 50 else file_name[:47] + "..."
    
    # Header
    st.markdown(f"<strong>{display_name}</strong>", unsafe_allow_html=True)
    st.caption(f"📅 {file_info['year']} | 💾 {file_info['size_mb']:.2f} MB | 📁 {file_info['category'].replace('_', ' ').title()[2:]}")
    st.markdown("---")
    
    # Read PDF and encode to base64
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        # Encode to base64
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Display PDF using browser's native viewer
        pdf_display = f'''
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="700"
            type="application/pdf"
            style="border: none;"
        >
            <p>Browser Anda tidak support PDF viewer. 
            <a href="data:application/pdf;base64,{base64_pdf}" download="{filename}">Download PDF</a></p>
        </iframe>
        '''
        
        st.markdown(pdf_display, unsafe_allow_html=True)
                
    except Exception as e:
        st.error(f"Error loading PDF: {e}")


def render_pdf_preview():
    """Check if PDF is selected and open viewer dialog"""
    if 'selected_pdf' in st.session_state and st.session_state['selected_pdf']:
        show_pdf_viewer()
