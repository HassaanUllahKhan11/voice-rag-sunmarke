@echo off
echo Starting Streamlit app...
echo.
echo Make sure you've:
echo 1. Installed dependencies: pip install -r requirements.txt
echo 2. Created .env file with API keys
echo 3. Run ingestion: python ingest.py
echo.
echo Starting app on http://localhost:8501
echo.
streamlit run app.py
pause
