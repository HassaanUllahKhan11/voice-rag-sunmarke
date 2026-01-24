"""
Quick verification script to check if all dependencies are installed correctly.
Run this before running the main application.
"""

import sys

def check_imports():
    """Check if all required imports are available."""
    print("Checking dependencies...")
    
    required_modules = [
        ("streamlit", "Streamlit"),
        ("chromadb", "ChromaDB"),
        ("langchain_community", "LangChain Community"),
        ("sentence_transformers", "Sentence Transformers"),
        ("faster_whisper", "Faster Whisper"),
        ("gtts", "Google Text-to-Speech"),
        ("google.generativeai", "Google Generative AI"),
        ("openai", "OpenAI (for DeepSeek)"),
        ("aiohttp", "aiohttp"),
        ("beautifulsoup4", "BeautifulSoup4"),
        ("selenium", "Selenium"),
        ("undetected_chromedriver", "Undetected ChromeDriver"),
        ("dotenv", "python-dotenv"),
        ("tiktoken", "tiktoken"),
    ]
    
    missing = []
    for module_name, display_name in required_modules:
        try:
            __import__(module_name)
            print(f"✓ {display_name}")
        except ImportError:
            print(f"✗ {display_name} - MISSING")
            missing.append(display_name)
    
    if missing:
        print(f"\n❌ Missing dependencies: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    else:
        print("\n✓ All dependencies are installed!")
        return True

def check_env_file():
    """Check if .env file exists."""
    import os
    if os.path.exists(".env"):
        print("✓ .env file found")
        return True
    else:
        print("⚠ .env file not found")
        print("  Copy env.example to .env and add your API keys")
        return False

def check_chromadb():
    """Check if ChromaDB has been initialized."""
    import os
    db_path = "./chroma_db"
    if os.path.exists(db_path) and os.listdir(db_path):
        print("✓ ChromaDB appears to be initialized")
        return True
    else:
        print("⚠ ChromaDB not initialized")
        print("  Run: python ingest.py")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Voice RAG Agent - Setup Verification")
    print("=" * 60)
    print()
    
    imports_ok = check_imports()
    print()
    env_ok = check_env_file()
    print()
    db_ok = check_chromadb()
    print()
    
    print("=" * 60)
    if imports_ok and env_ok and db_ok:
        print("✓ Setup complete! You can run: streamlit run app.py")
    else:
        print("⚠ Please complete the setup steps above")
    print("=" * 60)
