import os
import html
import fitz
import streamlit as st
from typing import Dict, List, Optional
from urllib.parse import quote
from src.config.settings import Settings
from src.utils.catalog import document_info
from src.utils.metadata import get_meta

def get_dataset_files() -> Dict[str, List[Dict]]:
    dataset_dir = Settings.DATASET_DIR
    files_by_category = {}
    
    if not os.path.exists(dataset_dir):
        return {}
    
    # Iterate through subdirectories
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

        # Skip folders without PDFs (e.g. leftover empty working folders)
        if not files_by_category[category]:
            del files_by_category[category]

    return files_by_category


def render_dataset_browser():
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
    
    # Tree view with expanders for each category
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


def pdfjs_viewer_url(pdf_path: str, page: int = 1, search: Optional[str] = None) -> str:
    """URL of the bundled PDF.js viewer (static/pdfjs) opened at a given page,
    optionally highlighting a phrase (used for cited sources)"""
    relative = os.path.relpath(pdf_path, Settings.STATIC_DIR).replace(os.sep, "/")
    # The file param is resolved relative to static/pdfjs/web/viewer.html
    file_param = quote(f"../../{relative}", safe="")
    # auto = fit the page width, capped at 125%, like the default zoom of Chrome's viewer.
    # No leading slash: Streamlit Cloud serves the app under /~/+/, so the URL must stay
    # relative to the app's own URL (see show_pdf_viewer).
    url = f"app/static/pdfjs/web/viewer.html?file={file_param}#page={page}&zoom=auto"
    if search:
        url += f"&search={quote(search)}&phrase=true"
    return url


# Tall dialog: equal 12px gaps above and below, the viewer fills whatever height the
# (possibly wrapping) title leaves, and the width gives pages roughly the size Chrome's
# PDF viewer opens them at. Phones are capped by the screen width instead.
PDF_DIALOG_CSS = """
<style>
[data-testid="stDialog"] {
    padding: 0 !important;
    align-items: center !important;
}
[data-testid="stDialog"] > div {
    margin: 12px !important;
    width: 920px !important;
    max-width: calc(100% - 24px) !important;
}
[role="dialog"] {
    height: calc(100vh - 24px);
    flex-direction: column;
}
[role="dialog"] h2 {
    font-size: 1rem !important;
    font-weight: 400 !important;
    padding-bottom: 0.25rem !important;
}
[role="dialog"] > div:last-child,
[role="dialog"] > div:last-child [data-testid="stVerticalBlock"],
[role="dialog"] > div:last-child [data-testid="stLayoutWrapper"],
[role="dialog"] [data-testid="stElementContainer"]:has(> iframe) {
    flex: 1 1 auto;
    min-height: 0;
    height: 100% !important;
}
[role="dialog"] iframe[data-testid="stIFrame"] {
    height: 100% !important;
}
/* PDF.js needs at least 350px of width, so phones get an edge-to-edge dialog */
@media (max-width: 640px) {
    [data-testid="stDialog"] > div {
        margin: 12px 0 !important;
        max-width: 100% !important;
    }
    [role="dialog"] > div:last-child {
        padding: 0 0 12px !important;
    }
    [role="dialog"] h2 {
        padding-left: 12px !important;
    }
}
</style>
"""


# st.iframe passes "/..." URLs through as-is, so they resolve against the domain root,
# which on Streamlit Cloud is the Cloud shell rather than the app (served under /~/+/).
# A srcdoc document inherits the app page's base URL, so a relative src inside it
# resolves correctly both locally and on Cloud.
PDF_FRAME_HTML = """<!doctype html>
<html><head><style>
html, body { margin: 0; height: 100%; overflow: hidden; }
iframe { display: block; width: 100%; height: 100%; border: 0; }
</style></head>
<body><iframe src="__SRC__" allow="fullscreen"></iframe></body></html>"""


def show_pdf_viewer(file_info: Dict):
    st.html(PDF_DIALOG_CSS)

    # Streamlit Cloud runs the app in a sandboxed iframe where Chrome blocks its native
    # PDF viewer. PDF.js (Firefox's viewer) is plain JavaScript, so it works inside the
    # sandbox and on mobile.
    viewer_url = pdfjs_viewer_url(file_info['path'], file_info.get('page', 1), file_info.get('search'))
    st.iframe(PDF_FRAME_HTML.replace("__SRC__", html.escape(viewer_url)), height=Settings.PDF_VIEWER_HEIGHT)


def pdf_dialog_title(file_info: Dict) -> str:
    """Dialog title: the document's catalog title"""
    return f"**{document_info(file_info['filename'])['title']}**"


def open_pdf(file_info: Dict):
    """Select a PDF to show in the viewer dialog on this run (usable as a widget callback).
    file_info needs 'path' and 'filename'; 'page' and 'search' are optional."""
    st.session_state['selected_pdf'] = file_info


def _close_pdf():
    # Without this the dialog would reopen on every later rerun (e.g. when sending a question)
    st.session_state['selected_pdf'] = None


def render_pdf_preview():
    if 'selected_pdf' in st.session_state and st.session_state['selected_pdf']:
        file_info = st.session_state['selected_pdf']
        # Build the dialog per document so its title can carry the document's name
        st.dialog(pdf_dialog_title(file_info), width="small", on_dismiss=_close_pdf)(show_pdf_viewer)(file_info)
