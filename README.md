# Voice-Enabled RAG AI Agent

A production-quality prototype of a voice-enabled RAG (Retrieval-Augmented Generation) AI agent that answers questions about Sunmarke.com using content from the website.

## Features

- 🕷️ **Web Scraping**: Automatically scrapes and ingests content from sunmarke.com
- 🗄️ **Local Vector Store**: Uses ChromaDB for local embedding storage
- 🔍 **RAG Implementation**: Retrieves relevant context before answering
- 🎤 **Voice Input**: Speech-to-text using Whisper
- 🤖 **Multi-LLM Comparison**: Queries Gemini, DeepSeek, and Kimi in parallel
- 📊 **3-Column UI**: Side-by-side comparison of all 3 responses
- 🔊 **Text-to-Speech**: Audio playback for each response
- 🛡️ **Strict Content-Only**: Only answers based on website content

## Project Structure

```
voice-rag-sunmarke/
├── ingest.py          # Web scraping and ChromaDB ingestion
├── retriever.py       # RAG retriever with strict prompts
├── llm_chains.py      # Async parallel LLM queries
├── app.py             # Streamlit UI
├── requirements.txt   # Python dependencies
├── env.example        # Environment variables template
├── chroma_db/         # ChromaDB vector store (created after ingestion)
├── data/              # Scraped data cache
└── audio_cache/       # TTS audio cache
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd voice-rag-sunmarke
pip install -r requirements.txt
```

**Note**: 
- **Chrome Browser Required**: Selenium requires Google Chrome to be installed on your system
- The scraper uses `undetected-chromedriver` which automatically downloads the ChromeDriver
- On Windows, you may need to install PyAudio dependencies separately (if using audio features):
  - Download PyAudio wheel from [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)
  - Or use: `pip install pipwin && pipwin install pyaudio`

### 2. Configure API Keys

1. Copy `env.example` to `.env`:
   ```bash
   copy env.example .env
   ```

2. Edit `.env` and add your API keys:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   KIMI_API_KEY=your_kimi_api_key_here
   KIMI_BASE_URL=https://api.moonshot.cn
   ```

**Getting API Keys**:
- **Gemini**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **DeepSeek**: Get from [DeepSeek Platform](https://platform.deepseek.com/)
- **Kimi**: Get from [Moonshot AI](https://platform.moonshot.cn/)

### 3. Verify Setup (Optional)

Check if all dependencies are installed:

```bash
python verify_setup.py
```

### 4. Ingest Website Content

Run the ingestion script to scrape and index sunmarke.com:

```bash
python ingest.py
```

This will:
- Scrape pages from sunmarke.com (max depth 3, max 100 pages)
- Clean and chunk the content
- Generate embeddings
- Store in ChromaDB

**Expected time**: 5-15 minutes depending on website size and network speed.

**Note**: The scraper uses `httpx` for web scraping. If you encounter 403 Forbidden errors, the website may have strict bot protection. 

**Fallback Option - Manual HTML Files**:
If web scraping fails, the script will automatically look for HTML files in a `data/` directory:
1. Create a `data/` folder in the project directory
2. Manually save HTML pages from sunmarke.com:
   - Open pages in your browser
   - Right-click → "Save Page As" → Choose "Web Page, HTML Only"
   - Save files to the `data/` directory
3. Run `python ingest.py` again - it will automatically load HTML files

The scraper will try web scraping first, then fall back to local HTML files if scraping fails.

### 5. Run the Streamlit App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

**If Streamlit doesn't start:**
- Make sure you're in the `voice-rag-sunmarke` directory
- Check if port 8501 is already in use: `streamlit run app.py --server.port 8502`
- Run `python test_streamlit.py` to check for import errors
- See `TROUBLESHOOTING.md` for detailed solutions

## Usage

### Text Queries
1. Type your question in the text input field
2. Click "Submit Text Query"
3. View responses from all 3 LLMs side-by-side
4. Click audio playback buttons to hear responses

### Voice Queries
1. Click the microphone icon or use the audio input
2. Record your question
3. The app will transcribe using Whisper
4. View and compare responses from all 3 LLMs

### Example Questions
- "What programs does Sunmarke offer?"
- "Tell me about admissions at Sunmarke"
- "What is the school's philosophy?"
- "How can I contact Sunmarke?"

## How It Works

1. **Ingestion** (`ingest.py`):
   - Crawls sunmarke.com with depth control
   - Extracts and cleans text content
   - Chunks intelligently using headers and token limits
   - Generates embeddings using sentence-transformers
   - Stores in ChromaDB

2. **Retrieval** (`retriever.py`):
   - Uses LangChain with ChromaDB
   - Retrieves top-k relevant documents
   - Formats context with source information
   - Creates strict anti-hallucination prompts

3. **LLM Queries** (`llm_chains.py`):
   - Runs async parallel queries to all 3 LLMs
   - Each LLM receives the same RAG prompt
   - Graceful error handling (one failure doesn't break others)

4. **UI** (`app.py`):
   - Streamlit interface
   - Voice recording and transcription
   - 3-column response comparison
   - Text-to-speech playback

## Error Handling

- **Missing API Keys**: App will show warnings for unavailable models
- **Network Errors**: Individual model failures are isolated
- **Empty Retrievals**: Gracefully handles queries with no relevant context
- **Out-of-Scope Questions**: Models are instructed to redirect to Sunmarke content only

## Technical Details

- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **STT**: OpenAI Whisper (base model)
- **TTS**: Google Text-to-Speech (gTTS)
- **Vector Store**: ChromaDB (local, persistent)
- **Chunking**: ~600 tokens per chunk with 100 token overlap
- **Retrieval**: Top-5 most similar documents

## Troubleshooting

### ChromaDB not found
- Run `ingest.py` first to create the vector store

### Whisper model download fails
- Check internet connection
- Whisper downloads models on first use (~150MB for base model)

### API errors

**Common Issues:**

1. **Gemini 404 Error**: The model name has been updated to `gemini-1.5-flash`. If you still get errors, check [Google AI Studio](https://makersuite.google.com/app/apikey) for available models.

2. **Insufficient Balance (402/429 errors)**: 
   - DeepSeek: Recharge your account at [DeepSeek Platform](https://platform.deepseek.com/)
   - Kimi: Recharge your account at [Moonshot AI](https://platform.moonshot.cn/)
   - Gemini: Check your Google Cloud billing

3. **Invalid API Key**: 
   - Verify API keys in `.env` file
   - Make sure keys are active and not expired
   - Check API documentation for correct key format

4. **Rate Limits**: 
   - Wait a few minutes and try again
   - Check your API plan limits
   - Consider upgrading your plan if needed

### Audio recording not working
- On Windows, may need to install PyAudio separately
- Try using text input if audio fails

## Local Development Notes

- All data stored locally (no cloud dependencies except API calls)
- ChromaDB persists between runs
- Scraped content cached in `data/` directory
- Audio files cached in `audio_cache/`

## License

This is a prototype project for local use only.
