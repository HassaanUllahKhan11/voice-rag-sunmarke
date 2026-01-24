"""
FastAPI entry point for Vercel deployment.
Exposes the Voice RAG functionality via REST API.
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Add the parent directory to the path to import llm module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.chains import get_parallel_query

# FastAPI app
app = FastAPI(
    title="Voice RAG API",
    description="Sunmarke School Voice RAG System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    results: Dict[str, Any]
    timestamp: str
    total_models: int

class HealthResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    available_models: list

@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        parallel_query = get_parallel_query()
        available_models = parallel_query.get_available_models()
        
        return HealthResponse(
            status="healthy",
            message=f"Voice RAG API is running with {len(available_models)} models",
            timestamp=datetime.now().isoformat(),
            available_models=available_models
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a query using all available LLM models."""
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Get the parallel query instance
        parallel_query = get_parallel_query()
        
        # Query all models
        results = await parallel_query.query_all(request.query.strip())
        
        return QueryResponse(
            results=results,
            timestamp=datetime.now().isoformat(),
            total_models=len(results)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

@app.get("/models")
async def get_available_models():
    """Get list of available models."""
    try:
        parallel_query = get_parallel_query()
        models = parallel_query.get_available_models()
        
        return {
            "available_models": models,
            "total_count": len(models),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")

# Vercel compatibility
handler = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)