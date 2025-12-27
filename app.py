"""
Streamlit Cloud Compatibility Wrapper
Executes the actual app from frontend/app.py
"""
import os
import sys

# Ensure we can import from current directory
sys.path.insert(0, os.path.dirname(__file__))

# Execute the actual Streamlit app
app_path = os.path.join(os.path.dirname(__file__), 'frontend', 'app.py')
with open(app_path, 'r', encoding='utf-8') as f:
    exec(f.read())