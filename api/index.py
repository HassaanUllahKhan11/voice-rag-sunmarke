"""
Voice RAG API for Vercel deployment - All-in-one file with embedded LLM logic.
"""

import json
import os
import asyncio
import logging
from http.server import BaseHTTPRequestHandler
from datetime import datetime
from typing import Dict, List

# LLM dependencies
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# LLM Chain Classes (Embedded)
# ------------------------------------------------------------------
class LLMChain:
    def __init__(self, name: str, model_name: str):
        self.name = name
        self.model_name = model_name
        self.error_count = 0

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")
        
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        logger.info(f"🔧 Creating AsyncOpenAI client for {name} with base_url: {base_url}")
        
        try:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers={
                    "HTTP-Referer": "https://voice-rag-sunmarke.vercel.app",
                    "X-Title": "Voice RAG Sunmarke API"
                }
            )
            logger.info(f"✅ AsyncOpenAI client created successfully for {name}")
        except Exception as client_error:
            logger.error(f"❌ Failed to create AsyncOpenAI client for {name}: {client_error}")
            raise

    async def generate(self, prompt: str) -> Dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful AI assistant specializing in Sunmarke School information. "
                            "Answer ONLY using the provided website content. "
                            "If the answer is not in the content, say you don't know."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            return {
                "model": self.name,
                "response": response.choices[0].message.content,
                "error": False,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return self.handle_error(e)

    def handle_error(self, error: Exception) -> Dict:
        self.error_count += 1
        logger.error(f"{self.name} error: {error}")

        msg = str(error).lower()

        if "402" in msg or "insufficient" in msg:
            friendly = "Insufficient OpenRouter balance. Please add credits."
        elif "429" in msg:
            friendly = "Rate limit exceeded. Try again shortly."
        elif "401" in msg:
            friendly = "Invalid OpenRouter API key."
        elif "404" in msg:
            friendly = f"Model not found: {self.model_name}"
        else:
            friendly = str(error)

        return {
            "model": self.name,
            "response": friendly,
            "error": True,
            "timestamp": datetime.now().isoformat(),
        }


class ParallelLLMQuery:
    def __init__(self):
        self.models = {
            "gemini": "google/gemini-2.5-flash",
            "deepseek": "deepseek/deepseek-r1-0528:free", 
            "kimi": "moonshotai/kimi-k2-0905"
        }
        self.chains = {}
        self.initialization_errors = {}
        
        # Debug environment first
        api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        logger.info(f"🔧 Initializing with API key present: {bool(api_key)}, Base URL: {base_url}")
        
        # Initialize each model with detailed error handling
        for key, model_name in self.models.items():
            try:
                logger.info(f"🔄 Attempting to initialize {key} ({model_name})")
                chain = LLMChain(name=key.title(), model_name=model_name)
                self.chains[key] = chain
                logger.info(f"✅ {key.title()} chain initialized successfully: {model_name}")
            except Exception as e:
                error_msg = f"Failed to initialize {key}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                self.initialization_errors[key] = error_msg
                continue
        
        logger.info(f"✅ {len(self.chains)} out of {len(self.models)} OpenRouter LLM chains initialized")
        if self.initialization_errors:
            logger.error(f"❌ Initialization errors: {self.initialization_errors}")
    
    def get_initialization_status(self):
        """Get detailed status of model initialization."""
        return {
            "total_models": len(self.models),
            "active_models": len(self.chains),
            "active_model_names": list(self.chains.keys()),
            "failed_models": self.initialization_errors
        }

    async def query_all(self, prompt: str) -> Dict[str, Dict]:
        if not self.chains:
            return {"error": "No LLM chains available"}
            
        tasks = {
            name: chain.generate(prompt)
            for name, chain in self.chains.items()
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        output = {}
        for (name, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                output[name] = {
                    "model": name,
                    "response": str(result),
                    "error": True,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                output[name] = result

        return output

    def get_available_models(self) -> List[str]:
        return list(self.chains.keys())


# Global LLM instance
_parallel_query = None

def get_parallel_query() -> ParallelLLMQuery:
    global _parallel_query
    if _parallel_query is None:
        _parallel_query = ParallelLLMQuery()
    return _parallel_query


# ------------------------------------------------------------------
# HTTP Handler
# ------------------------------------------------------------------
class handler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        """Set CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def _send_json_response(self, status_code, data):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._set_cors_headers()
        self.end_headers()
        
        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode())
    
    def _send_error_response(self, status_code, message):
        """Send error response."""
        error_data = {
            "error": message,
            "timestamp": datetime.now().isoformat()
        }
        self._send_json_response(status_code, error_data)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        try:
            path = self.path
            
            if path in ["/", "/api"]:
                # Health check with detailed LLM status
                try:
                    parallel_query = get_parallel_query()
                    available_models = parallel_query.get_available_models()
                    initialization_status = parallel_query.get_initialization_status()
                    
                    if available_models:
                        llm_status = f"LLM integration active with {len(available_models)} models: {', '.join(available_models)}"
                    else:
                        llm_status = f"LLM integration failed - No models active. Check initialization_details."
                        
                except Exception as llm_error:
                    llm_status = f"LLM integration error: {str(llm_error)}"
                    available_models = []
                    initialization_status = {"error": str(llm_error)}
                
                response_data = {
                    "status": "healthy",
                    "message": "Voice RAG API for Sunmarke School",
                    "llm_status": llm_status,
                    "available_models": available_models,
                    "initialization_details": initialization_status,
                    "timestamp": datetime.now().isoformat(),
                    "endpoints": {
                        "GET /": "Health check and system status",
                        "POST /query": "Process Voice RAG queries about Sunmarke School",
                        "GET /models": "List available LLM models"
                    },
                    "environment_check": {
                        "openrouter_key": "Present" if os.getenv("OPENROUTER_API_KEY") else "Missing - Set in Vercel Dashboard",
                        "openrouter_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                    }
                }
                self._send_json_response(200, response_data)
                
            elif path in ["/models", "/api/models"]:
                try:
                    parallel_query = get_parallel_query()
                    models = parallel_query.get_available_models()
                    
                    response_data = {
                        "available_models": models,
                        "total_count": len(models),
                        "timestamp": datetime.now().isoformat()
                    }
                    self._send_json_response(200, response_data)
                except Exception as e:
                    self._send_error_response(500, f"Failed to get models: {str(e)}")
                
            else:
                self._send_error_response(404, f"Endpoint not found: {path}")
                
        except Exception as e:
            self._send_error_response(500, f"Internal server error: {str(e)}")
    
    def do_POST(self):
        """Handle POST requests."""
        try:
            path = self.path
            
            if path in ["/query", "/api/query"]:
                # Read request body
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    self._send_error_response(400, "Request body is required")
                    return
                
                post_data = self.rfile.read(content_length)
                try:
                    request_data = json.loads(post_data.decode())
                except json.JSONDecodeError:
                    self._send_error_response(400, "Invalid JSON in request body")
                    return
                
                query = request_data.get("query", "").strip()
                if not query:
                    self._send_error_response(400, "Query cannot be empty. Please ask something about Sunmarke School.")
                    return
                
                # Check environment variables
                if not os.getenv("OPENROUTER_API_KEY"):
                    self._send_error_response(500, "OpenRouter API key not configured. Please set OPENROUTER_API_KEY in Vercel Dashboard.")
                    return
                
                # Process with LLM
                try:
                    # Enhanced query for better context
                    enhanced_query = f"""Using the Sunmarke School website content, please answer: {query}
                    
                    If the information is not in the content, please say so clearly."""
                    
                    # Get the parallel query instance
                    parallel_query = get_parallel_query()
                    
                    # Handle asyncio for serverless
                    try:
                        results = asyncio.run(parallel_query.query_all(enhanced_query))
                    except RuntimeError as e:
                        if "cannot be called from a running event loop" in str(e):
                            # Handle nested event loop issue
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, parallel_query.query_all(enhanced_query))
                                results = future.result(timeout=30)
                        else:
                            raise e
                    
                    response_data = {
                        "query": query,
                        "results": results,
                        "timestamp": datetime.now().isoformat(),
                        "total_models": len(results) if isinstance(results, dict) else 0,
                        "note": "Responses based on Sunmarke School website content"
                    }
                    self._send_json_response(200, response_data)
                    
                except Exception as llm_error:
                    # Fallback response if LLM fails
                    response_data = {
                        "query": query,
                        "error": f"LLM processing failed: {str(llm_error)}",
                        "fallback_response": "I apologize, but I'm experiencing technical difficulties accessing the LLM models. Please ensure the OpenRouter API key is properly configured.",
                        "timestamp": datetime.now().isoformat()
                    }
                    self._send_json_response(500, response_data)
                
            else:
                self._send_error_response(404, f"POST endpoint not found: {path}")
                
        except Exception as e:
            self._send_error_response(500, f"Query processing failed: {str(e)}")
    
    def log_message(self, format, *args):
        """Override to reduce log noise."""
        return