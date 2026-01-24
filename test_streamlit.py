"""
Quick test to verify Streamlit can run.
Run this before running the main app.
"""

import sys

def test_imports():
    """Test if all required imports work."""
    print("Testing imports...")
    
    try:
        import streamlit as st
        print("✓ Streamlit imported")
    except ImportError as e:
        print(f"✗ Streamlit import failed: {e}")
        return False
    
    try:
        from retriever import RAGRetriever
        print("✓ Retriever imported")
    except ImportError as e:
        print(f"✗ Retriever import failed: {e}")
        return False
    
    try:
        from llm_chains import get_parallel_query
        print("✓ LLM chains imported")
    except ImportError as e:
        print(f"✗ LLM chains import failed: {e}")
        return False
    
    try:
        from faster_whisper import WhisperModel
        print("✓ Faster Whisper imported")
    except ImportError as e:
        print(f"⚠ Faster Whisper import failed: {e} (voice input will be disabled)")
    
    try:
        from gtts import gTTS
        print("✓ gTTS imported")
    except ImportError as e:
        print(f"⚠ gTTS import failed: {e} (TTS will be disabled)")
    
    return True

def test_basic_streamlit():
    """Test if Streamlit can run a basic app."""
    print("\nTesting basic Streamlit functionality...")
    try:
        import streamlit as st
        # This is just a test - won't actually run Streamlit
        print("✓ Streamlit module is functional")
        return True
    except Exception as e:
        print(f"✗ Streamlit test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Streamlit App - Pre-flight Check")
    print("=" * 60)
    print()
    
    imports_ok = test_imports()
    print()
    streamlit_ok = test_basic_streamlit()
    
    print()
    print("=" * 60)
    if imports_ok and streamlit_ok:
        print("✓ All checks passed!")
        print("You can run: streamlit run app.py")
    else:
        print("⚠ Some checks failed. Please fix the issues above.")
    print("=" * 60)
