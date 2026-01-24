"""
Simple test version for debugging Vercel serverless function.
"""

import json
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
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        try:
            response_data = {
                "status": "healthy",
                "message": "Voice RAG API test version is running",
                "timestamp": datetime.now().isoformat(),
                "endpoints": {
                    "GET /": "Health check (this endpoint)",
                    "POST /query": "Test query endpoint"
                },
                "debug_info": {
                    "python_path": __file__,
                    "environment": "Vercel Serverless"
                }
            }
            self._send_json_response(200, response_data)
                
        except Exception as e:
            error_data = {
                "error": f"GET error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            self._send_json_response(500, error_data)
    
    def do_POST(self):
        """Handle POST requests."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    request_data = json.loads(post_data.decode())
                    query = request_data.get("query", "")
                except:
                    query = "Invalid JSON"
            else:
                query = "No query provided"
            
            response_data = {
                "status": "received",
                "query": query,
                "response": "This is a test response. LLM integration will be added once basic functionality is confirmed.",
                "timestamp": datetime.now().isoformat(),
                "note": "Test version - not connected to LLMs yet"
            }
            self._send_json_response(200, response_data)
                
        except Exception as e:
            error_data = {
                "error": f"POST error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            self._send_json_response(500, error_data)
    
    def log_message(self, format, *args):
        """Override to reduce log noise."""
        return