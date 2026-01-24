# Troubleshooting Guide

## Streamlit Not Working on Localhost

### Common Issues and Solutions

#### 1. Port Already in Use
**Error**: `Address already in use` or port 8501 is busy

**Solution**:
```bash
# Use a different port
streamlit run app.py --server.port 8502

# Or find and kill the process using port 8501
# On Windows PowerShell:
netstat -ano | findstr :8501
taskkill /PID <PID_NUMBER> /F
```

#### 2. Import Errors
**Error**: `ModuleNotFoundError` or import failures

**Solution**:
```bash
# Make sure you're in the correct directory
cd voice-rag-sunmarke

# Verify all dependencies are installed
pip install -r requirements.txt

# Test imports
python test_streamlit.py
```

#### 3. ChromaDB Not Found
**Error**: `Failed to load RAG retriever` or database errors

**Solution**:
```bash
# Run ingestion first to create the database
python ingest.py

# Make sure chroma_db/ directory exists
# If not, run ingestion again
```

#### 4. API Keys Missing
**Error**: LLM API errors or authentication failures

**Solution**:
1. Check that `.env` file exists (copy from `env.example`)
2. Verify all API keys are set:
   - `GOOGLE_API_KEY`
   - `DEEPSEEK_API_KEY`
   - `KIMI_API_KEY`
3. Restart Streamlit after adding keys

#### 5. Streamlit Not Starting
**Error**: Nothing happens when running `streamlit run app.py`

**Solution**:
```bash
# Check Streamlit installation
pip show streamlit

# Reinstall if needed
pip install --upgrade streamlit

# Try running with verbose output
streamlit run app.py --logger.level=debug
```

#### 6. Browser Not Opening Automatically
**Solution**:
- Manually open: `http://localhost:8501`
- Check firewall settings
- Try: `http://127.0.0.1:8501`

#### 7. Windows-Specific Issues

**PowerShell Execution Policy**:
```powershell
# If you get execution policy errors
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Path Issues**:
- Make sure you're in the `voice-rag-sunmarke` directory
- Use full paths if needed: `python C:\path\to\voice-rag-sunmarke\app.py`

### Quick Diagnostic Steps

1. **Test Streamlit Installation**:
   ```bash
   streamlit --version
   ```

2. **Test Imports**:
   ```bash
   python test_streamlit.py
   ```

3. **Check ChromaDB**:
   ```bash
   # Should see chroma_db/ directory
   dir chroma_db
   ```

4. **Verify Environment**:
   ```bash
   python verify_setup.py
   ```

5. **Run with Debug**:
   ```bash
   streamlit run app.py --logger.level=debug
   ```

### Getting Help

If issues persist:
1. Check the terminal/console for error messages
2. Look at Streamlit's error display in the browser
3. Check `~/.streamlit/logs/` for log files
4. Verify all steps in README.md were completed
