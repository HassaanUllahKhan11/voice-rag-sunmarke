"""
RAG Retriever using LangChain and ChromaDB.
Implements strict retrieval with anti-hallucination prompts.
"""

import os
import logging
from typing import List, Dict

from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
try:
    # LangChain 0.1+ imports
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_core.documents import Document
except ImportError:
    # Fallback for older versions
    from langchain.vectorstores import Chroma
    from langchain.embeddings import HuggingFaceEmbeddings
    from langchain.schema import Document
from sentence_transformers import SentenceTransformer

load_dotenv()
logger = logging.getLogger(__name__)


class RAGRetriever:
    """RAG retriever with strict content-only answering."""
    
    def __init__(self, db_path: str = "./chroma_db", k: int = 5):
        self.db_path = db_path
        self.k = k
        
        # Initialize embeddings (must match ingest.py)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Initialize ChromaDB vector store
        self.vectorstore = Chroma(
            persist_directory=db_path,
            embedding_function=self.embeddings,
            collection_name="sunmarke_content"
        )
        
        logger.info(f"RAG Retriever initialized with k={k}")
    
    def retrieve(self, query: str, k: int = None) -> List[Document]:
        """Retrieve relevant documents for a query."""
        k = k or self.k
        try:
            docs = self.vectorstore.similarity_search(query, k=k)
            logger.info(f"Retrieved {len(docs)} documents for query: {query[:50]}...")
            return docs
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            return []
    
    def retrieve_with_scores(self, query: str, k: int = None) -> List[tuple]:
        """Retrieve documents with similarity scores."""
        k = k or self.k
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            logger.info(f"Retrieved {len(results)} documents with scores")
            return results
        except Exception as e:
            logger.error(f"Error retrieving documents with scores: {e}")
            return []
    
    def format_context(self, documents: List[Document]) -> str:
        """Format retrieved documents into context string."""
        if not documents:
            return "No relevant information found in the knowledge base."
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            metadata = doc.metadata
            url = metadata.get('url', 'Unknown')
            title = metadata.get('title', 'Untitled')
            section = metadata.get('section', '')
            
            context_parts.append(
                f"[Source {i}]\n"
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"{f'Section: {section}' if section else ''}\n"
                f"Content: {doc.page_content}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    @staticmethod
    def get_strict_prompt_template() -> str:
        """Get the strict anti-hallucination prompt template."""
        return """You are a helpful assistant that answers questions STRICTLY based on the provided context from the Sunmarke website.

CRITICAL RULES:
1. ONLY use information from the provided context below
2. If the context does not contain enough information to answer the question, say: "I don't have enough information in the knowledge base to answer this question accurately."
3. DO NOT make up, infer, or guess information that is not explicitly stated in the context
4. DO NOT use any knowledge from your training data - only use the provided context
5. If asked about something not related to Sunmarke, politely redirect: "I can only answer questions about Sunmarke based on the website content."
6. Cite sources when possible (mention the URL or title from the context)

Context from Sunmarke website:
{context}

Question: {question}

Answer (based ONLY on the context above):"""


def create_rag_prompt(context: str, question: str) -> str:
    """Create a RAG prompt with context and question."""
    template = RAGRetriever.get_strict_prompt_template()
    return template.format(context=context, question=question)
