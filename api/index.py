"""
Voice RAG API for Vercel deployment with robust error handling.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from datetime import datetime

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
                # Try to import and initialize LLM chains
                try:
                    from llm.chains import get_parallel_query
                    parallel_query = get_parallel_query()
                    available_models = parallel_query.get_available_models()
                    llm_status = f"LLM integration active with {len(available_models)} models: {', '.join(available_models)}"
                except Exception as llm_error:
                    llm_status = f"LLM integration error: {str(llm_error)}"
                    available_models = []
                
                response_data = {
                    "status": "healthy",
                    "message": "Voice RAG API for Sunmarke School",
                    "llm_status": llm_status,
                    "available_models": available_models,
                    "timestamp": datetime.now().isoformat(),
                    "endpoints": {
                        "GET /": "Health check and system status",
                        "POST /query": "Process Voice RAG queries about Sunmarke School",
                        "GET /models": "List available LLM models"
                    },
                    "environment_check": {
                        "openrouter_key": "Present" if os.getenv("OPENROUTER_API_KEY") else "Missing - Set in Vercel Dashboard",
                        "openrouter_url": os.getenv("OPENROUTER_BASE_URL", "Not set")
                    }
                }
                self._send_json_response(200, response_data)
                
            elif path in ["/models", "/api/models"]:
                try:
                    from llm.chains import get_parallel_query
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
                
                # Try to process with LLM
                try:
                    from llm.chains import get_parallel_query
                    import asyncio
                    
                    # Enhanced query for better context
                    enhanced_query = f"""Using the Sunmarke School website content, please answer: {query}
                    
                    If the information is not in the content, please say so clearly."""
                    
                    # Get the parallel query instance
                    parallel_query = get_parallel_query()
                    
                    # Run async function in sync context for serverless
                    try:
                        # Try to get existing event loop
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Create new loop if current one is running
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, parallel_query.query_all(enhanced_query))
                                results = future.result(timeout=30)
                        else:
                            results = loop.run_until_complete(parallel_query.query_all(enhanced_query))
                    except RuntimeError:
                        # No event loop, create new one
                        results = asyncio.run(parallel_query.query_all(enhanced_query))
                    
                    response_data = {
                        "query": query,
                        "results": results,
                        "timestamp": datetime.now().isoformat(),
                        "total_models": len(results),
                        "note": "Responses based on Sunmarke School website content"
                    }
                    self._send_json_response(200, response_data)
                    
                except Exception as llm_error:
                    # Fallback response if LLM fails
                    response_data = {
                        "query": query,
                        "error": f"LLM processing failed: {str(llm_error)}",
                        "fallback_response": "I apologize, but I'm experiencing technical difficulties accessing the LLM models. Please ensure the OpenRouter API key is properly configured in the Vercel environment variables.",
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