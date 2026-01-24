"""
Streamlit UI for Voice-Enabled RAG AI Agent
Features: Voice input, parallel LLM queries, 3-column comparison, TTS
"""

import os
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional

import streamlit as st
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from gtts import gTTS
import io
import base64

from retriever import RAGRetriever, create_rag_prompt
from llm_chains import get_parallel_query

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Voice RAG Agent - Sunmarke",
    page_icon="🎤",
    layout="wide"
)

# Initialize session state
if 'retriever' not in st.session_state:
    st.session_state.retriever = None
if 'whisper_model' not in st.session_state:
    st.session_state.whisper_model = None
if 'query_history' not in st.session_state:
    st.session_state.query_history = []
if 'current_responses' not in st.session_state:
    st.session_state.current_responses = {}


@st.cache_resource
def load_retriever():
    """Load RAG retriever (cached)."""
    try:
        retriever = RAGRetriever(db_path="./chroma_db", k=5)
        logger.info("RAG retriever loaded successfully")
        return retriever
    except Exception as e:
        logger.error(f"Failed to load retriever: {e}")
        st.error(f"Failed to load RAG retriever: {e}")
        return None


@st.cache_resource
def load_whisper_model():
    """Load Whisper model (cached)."""
    try:
        # faster-whisper uses WhisperModel instead of load_model
        model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully")
        return model
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        st.warning(f"Whisper model loading failed: {e}. Using text input only.")
        return None


def transcribe_audio(audio_file) -> Optional[str]:
    """Transcribe audio file to text using faster-whisper."""
    if st.session_state.whisper_model is None:
        return None
    
    try:
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_file.read())
            tmp_path = tmp_file.name
        
        # Transcribe using faster-whisper API
        segments, info = st.session_state.whisper_model.transcribe(tmp_path, beam_size=5)
        
        # faster-whisper returns segments, need to join them
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)
        
        text = " ".join(text_parts).strip()
        
        # Clean up
        os.unlink(tmp_path)
        
        logger.info(f"Transcribed audio: {text[:50]}...")
        return text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        st.error(f"Transcription failed: {e}")
        return None


def text_to_speech(text: str, lang: str = "en") -> Optional[bytes]:
    """Convert text to speech audio."""
    try:
        # gTTS requires internet connection to Google's servers
        tts = gTTS(text=text, lang=lang, slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        return audio_buffer.read()
    except Exception as e:
        # Handle connection errors gracefully
        error_msg = str(e).lower()
        if "connection" in error_msg or "network" in error_msg or "failed" in error_msg:
            logger.warning(f"TTS connection error (internet may be required): {e}")
        else:
            logger.error(f"TTS error: {e}")
        return None


def get_audio_html(audio_bytes: bytes) -> str:
    """Generate HTML audio player for audio bytes."""
    audio_b64 = base64.b64encode(audio_bytes).decode()
    return f"""
    <audio controls style="width: 100%;">
        <source src="data:audio/mpeg;base64,{audio_b64}" type="audio/mpeg">
        Your browser does not support the audio element.
    </audio>
    """


async def process_query(query: str) -> Dict[str, Dict]:
    """Process query through RAG and parallel LLMs."""
    try:
        if st.session_state.retriever is None:
            logger.error("Retriever not initialized")
            return {}
        
        # Retrieve relevant context
        documents = st.session_state.retriever.retrieve(query)
        context = st.session_state.retriever.format_context(documents)
        
        # Create RAG prompt
        rag_prompt = create_rag_prompt(context, query)
        
        # Query all LLMs in parallel
        parallel_query = get_parallel_query()
        results = await parallel_query.query_all(rag_prompt)
        
        return results
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        return {}


def main():
    """Main Streamlit app."""
    st.title("🎤 Voice-Enabled RAG AI Agent")
    st.markdown("**Ask questions about Sunmarke.com using voice or text**")
    
    # Initialize components
    if st.session_state.retriever is None:
        with st.spinner("Loading RAG retriever..."):
            st.session_state.retriever = load_retriever()
    
    if st.session_state.whisper_model is None:
        with st.spinner("Loading Whisper model (this may take a moment)..."):
            st.session_state.whisper_model = load_whisper_model()
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        st.info("This agent answers questions based ONLY on content from sunmarke.com")
        
        if st.button("Clear History"):
            st.session_state.query_history = []
            st.session_state.current_responses = {}
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Query History")
        for i, query in enumerate(reversed(st.session_state.query_history[-10:])):
            if st.button(f"Q{i+1}: {query[:30]}...", key=f"hist_{i}"):
                # Re-run query (simplified - in production, store full results)
                pass
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Text input
        text_query = st.text_input(
            "Enter your question:",
            placeholder="Ask about Sunmarke school, programs, admissions, etc.",
            key="text_input"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        submit_text = st.button("Submit Text Query", type="primary", use_container_width=True)
    
    # Voice input
    st.markdown("### 🎤 Voice Input")
    audio_file = st.audio_input("Record your question:")
    
    if audio_file is not None:
        with st.spinner("Transcribing audio..."):
            transcribed_text = transcribe_audio(audio_file)
            if transcribed_text:
                st.success(f"Transcribed: **{transcribed_text}**")
                text_query = transcribed_text
                submit_text = True
    
    # Process query
    if submit_text and text_query:
        st.session_state.query_history.append(text_query)
        
        # Show query
        st.markdown("---")
        st.markdown(f"### Query: {text_query}")
        
        # Process with loading indicators
        with st.spinner("Retrieving context and querying LLMs..."):
            try:
                # Run async function
                results = asyncio.run(process_query(text_query))
                st.session_state.current_responses = results
            except Exception as e:
                logger.error(f"Error processing query: {e}", exc_info=True)
                st.error(f"Error processing query: {e}")
                st.session_state.current_responses = {}
        
        # Display results in 3 columns
        if st.session_state.current_responses:
            cols = st.columns(3)
            
            model_names = {
                'gemini': '🤖 Gemini',
                'deepseek': '🔮 DeepSeek',
                'kimi': '🌙 Kimi'
            }
            
            for idx, (model_key, result) in enumerate(st.session_state.current_responses.items()):
                with cols[idx]:
                    model_display_name = model_names.get(model_key, model_key.title())
                    st.markdown(f"### {model_display_name}")
                    
                    # Error indicator
                    if result.get('error', False):
                        st.error("❌ Error occurred")
                        error_msg = result.get('response', 'Unknown error')
                        st.warning(error_msg)
                        # Show helpful tips for common errors
                        if 'insufficient balance' in error_msg.lower() or 'quota' in error_msg.lower():
                            st.info("💡 **Tip**: Recharge your API account or check your billing settings.")
                        elif 'api key' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                            st.info("💡 **Tip**: Check your `.env` file and verify your API keys are correct.")
                        elif 'model not found' in error_msg.lower() or '404' in error_msg.lower():
                            st.info("💡 **Tip**: The model name may have changed. Check the API documentation.")
                        else:
                            st.code(error_msg)
                    else:
                        # Response text
                        st.markdown(result.get('response', 'No response'))
                        
                        # TTS button
                        response_text = result.get('response', '')
                        if response_text and not result.get('error', False):
                            try:
                                audio_bytes = text_to_speech(response_text)
                                if audio_bytes:
                                    st.markdown("#### 🔊 Audio Playback")
                                    st.markdown(get_audio_html(audio_bytes), unsafe_allow_html=True)
                                else:
                                    st.caption("⚠️ Audio unavailable (internet required for TTS)")
                            except Exception as e:
                                logger.warning(f"TTS failed for {model_key}: {e}")
                                st.caption("⚠️ Audio unavailable")
                    
                    # Timestamp
                    if 'timestamp' in result:
                        st.caption(f"Generated: {result['timestamp']}")
        else:
            st.warning("No responses received. Check API keys and network connection.")
    
    # Display previous results if available
    elif st.session_state.current_responses:
        st.markdown("---")
        st.markdown("### Previous Results")
        
        cols = st.columns(3)
        model_names = {
            'gemini': '🤖 Gemini',
            'deepseek': '🔮 DeepSeek',
            'kimi': '🌙 Kimi'
        }
        
        for idx, (model_key, result) in enumerate(st.session_state.current_responses.items()):
            with cols[idx]:
                model_display_name = model_names.get(model_key, model_key.title())
                st.markdown(f"### {model_display_name}")
                
                if result.get('error', False):
                    st.error("❌ Error occurred")
                    error_msg = result.get('response', 'Unknown error')
                    st.warning(error_msg)
                    # Show helpful tips for common errors
                    if 'insufficient balance' in error_msg.lower() or 'quota' in error_msg.lower():
                        st.info("💡 **Tip**: Recharge your API account or check your billing settings.")
                    elif 'api key' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                        st.info("💡 **Tip**: Check your `.env` file and verify your API keys are correct.")
                    elif 'model not found' in error_msg.lower() or '404' in error_msg.lower():
                        st.info("💡 **Tip**: The model name may have changed. Check the API documentation.")
                    else:
                        st.code(error_msg)
                else:
                    st.markdown(result.get('response', 'No response'))
                    
                    response_text = result.get('response', '')
                    if response_text and not result.get('error', False):
                        try:
                            audio_bytes = text_to_speech(response_text)
                            if audio_bytes:
                                st.markdown("#### 🔊 Audio Playback")
                                st.markdown(get_audio_html(audio_bytes), unsafe_allow_html=True)
                            else:
                                st.caption("⚠️ Audio playback unavailable (internet connection required for TTS)")
                        except Exception as e:
                            logger.warning(f"TTS failed for {model_key}: {e}")
                            st.caption("⚠️ Audio playback unavailable")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
        <p>Voice RAG Agent - Powered by ChromaDB, LangChain, and multiple LLMs</p>
        <p>Content source: <a href='https://www.sunmarke.com'>sunmarke.com</a></p>
        </div>
        """,
        unsafe_allow_html=True
    )


# Streamlit runs the code directly - no need for if __name__ == "__main__"
main()
