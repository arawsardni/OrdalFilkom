"""
Streamlit Cloud Compatibility Wrapper
This file exists for Streamlit Community Cloud deployment.
The actual app is in frontend/app.py
"""
import os
import sys

# Ensure we can import from current directory
sys.path.insert(0, os.path.dirname(__file__))

# Import and run the actual app
import frontend.app