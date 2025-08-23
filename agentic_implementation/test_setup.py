#!/usr/bin/env python3
"""
Test script to verify that the merged project can import all necessary modules
"""

def test_imports():
    """Test that all required modules can be imported"""
    try:
        print("Testing imports...")
        
        # Test frontend imports
        print("✓ Testing frontend imports...")
        from config import get_settings
        from data import SearchHit, CompanyReport
        from ui import render_report
        print("  ✓ Frontend modules imported successfully")
        
        # Test backend imports
        print("✓ Testing backend imports...")
        from backend.graph import Graph
        from backend.services.websocket_manager import WebSocketManager
        from backend.services.pdf_service import PDFService
        print("  ✓ Backend modules imported successfully")
        
        # Test FastAPI imports
        print("✓ Testing FastAPI imports...")
        import fastapi
        import uvicorn
        print("  ✓ FastAPI modules imported successfully")
        
        # Test Streamlit imports
        print("✓ Testing Streamlit imports...")
        import streamlit
        print("  ✓ Streamlit imported successfully")
        
        print("\n🎉 All imports successful! The merged project is ready to run.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install missing dependencies with: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_imports()
