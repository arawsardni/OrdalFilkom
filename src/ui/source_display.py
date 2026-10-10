import os
from typing import List, Dict
import streamlit as st

from src.config.settings import Settings
from src.ui.dataset_browser import open_pdf


def display_sources(sources_data: List[Dict], key_prefix: str):
    """List the pages the answer cites; each opens the PDF viewer at that page.

    key_prefix keeps widget keys unique when several answers are shown.
    """
    if not sources_data:
        return

    st.caption("Sumber (klik untuk membuka halamannya):")
    for source in sources_data:
        st.button(
            f"[{source['number']}] {source['title']} ({source['year']}), hal. {source['page']}",
            key=f"{key_prefix}_source_{source['number']}",
            on_click=open_pdf,
            args=(_viewer_file_info(source),),
            type="tertiary",
            icon=":material/description:",
        )


def _viewer_file_info(source: Dict) -> Dict:
    page = str(source['page'])
    return {
        'path': os.path.join(Settings.DATASET_DIR, source['category'], source['file_name']),
        'filename': source['file_name'],
        'page': int(page) if page.isdigit() else 1,
        'search': source.get('search'),
    }
