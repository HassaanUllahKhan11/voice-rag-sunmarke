"""
Python serverless function entry point for Vercel deployment.
Exposes the Voice RAG functionality via REST API.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from llm.chains import get_parallel_query

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
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path == "/" or path == "/api":
                # Health check endpoint
                parallel_query = get_parallel_query()
                available_models = parallel_query.get_available_models()
                
                response_data = {
                    "status": "healthy",
                    "message": f"Voice RAG API is running with {len(available_models)} models",
                    "timestamp": datetime.now().isoformat(),
                    "available_models": available_models
                }
                self._send_json_response(200, response_data)
                
            elif path == "/models" or path == "/api/models":
                # Get available models endpoint
                parallel_query = get_parallel_query()
                models = parallel_query.get_available_models()
                
                response_data = {
                    "available_models": models,
                    "total_count": len(models),
                    "timestamp": datetime.now().isoformat()
                }
                self._send_json_response(200, response_data)
                
            else:
                self._send_error_response(404, "Endpoint not found")
                
        except Exception as e:
            self._send_error_response(500, f"Internal server error: {str(e)}")
    
    def do_POST(self):
        """Handle POST requests."""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            if path == "/query" or path == "/api/query":
                # Process query endpoint
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
                    self._send_error_response(400, "Query cannot be empty")
                    return
                
                # Get the parallel query instance and process
                parallel_query = get_parallel_query()
                
                # Run async function in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(parallel_query.query_all(query))
                finally:
                    loop.close()
                
                response_data = {
                    "results": results,
                    "timestamp": datetime.now().isoformat(),
                    "total_models": len(results)
                }
                self._send_json_response(200, response_data)
                
            else:
                self._send_error_response(404, "Endpoint not found")
                
        except Exception as e:
            self._send_error_response(500, f"Query processing failed: {str(e)}")