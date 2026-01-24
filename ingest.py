"""
Content ingestion script for Sunmarke.com
Scrapes, cleans, chunks, and stores content in ChromaDB for RAG.
"""

import os
import re
import logging
import time
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import tiktoken
import httpx

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "https://www.sunmarke.com"
MAX_DEPTH = 3
MAX_PAGES = 100  # Safety limit
CHUNK_SIZE = 600  # Target tokens per chunk
CHUNK_OVERLAP = 100  # Overlap tokens between chunks

# Initialize embedding model
logger.info("Loading embedding model...")
EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
ENCODER = tiktoken.get_encoding("cl100k_base")  # For token counting


class WebScraper:
    """Scrapes content from Sunmarke.com with depth control using httpx."""
    
    def __init__(self, base_url: str, max_depth: int = 3, max_pages: int = 100):
        self.base_url = base_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.visited = set()
        self.pages = []

        self.client = httpx.Client(
            timeout=20.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "DNT": "1"
            },
            follow_redirects=True
        )

    def is_valid_url(self, url: str) -> bool:
        """Check if URL is valid for scraping."""
        parsed = urlparse(url)
        if parsed.netloc not in ["sunmarke.com", "www.sunmarke.com"]:
            return False
        if any(url.lower().endswith(ext) for ext in [
            ".pdf", ".jpg", ".png", ".svg", ".zip"
        ]):
            return False
        return True

    def extract_text(self, soup: BeautifulSoup) -> str:
        """Extract and clean text content."""
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        main = soup.find("main") or soup.find("article") or soup.body
        if not main:
            return ""

        return " ".join(main.stripped_strings)

    def scrape_page(self, url: str, retries: int = 3):
        """Scrape a single page with retry logic."""
        logger.info(f"Fetching {url}")
        
        for attempt in range(retries):
            try:
                # Add referer header for subsequent requests
                headers = {}
                if attempt > 0:
                    headers["Referer"] = self.base_url
                    time.sleep(1)  # Small delay between retries
                
                r = self.client.get(url, headers=headers)
                
                if r.status_code == 403:
                    logger.warning(f"403 Forbidden for {url}, attempt {attempt + 1}/{retries}")
                    if attempt < retries - 1:
                        # Try with different approach
                        continue
                    else:
                        logger.error(f"Failed to access {url} after {retries} attempts")
                        return None
                
                if r.status_code != 200:
                    logger.warning(f"HTTP {r.status_code} for {url}")
                    return None

                soup = BeautifulSoup(r.text, "lxml")
                text = self.extract_text(soup)

                if len(text) < 200:
                    logger.warning(f"Text too short for {url} ({len(text)} chars)")
                    return None

                title = soup.title.string.strip() if soup.title else url

                return {
                    "url": url,
                    "title": title,
                    "text": text,
                    "headers": []
                }
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error for {url}: {e}")
                if attempt == retries - 1:
                    return None
            except Exception as e:
                logger.warning(f"Error scraping {url} (attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    return None
                time.sleep(1)
        
        return None

    def find_links(self, soup: BeautifulSoup, current_url: str) -> List[str]:
        """Find all valid links on a page."""
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(current_url, a["href"]).split("#")[0]
            if self.is_valid_url(href) and href not in self.visited:
                links.append(href)
        return links

    def crawl(self) -> List[Dict]:
        """Crawl the website starting from base URL."""
        logger.info(f"Starting crawl of {self.base_url} using httpx")
        queue = [(self.base_url, 0)]

        while queue and len(self.pages) < self.max_pages:
            url, depth = queue.pop(0)
            if url in self.visited or depth > self.max_depth:
                continue

            self.visited.add(url)
            page = self.scrape_page(url)
            if not page:
                continue

            self.pages.append(page)

            # Get page again for link extraction
            try:
                r = self.client.get(url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "lxml")
                    for link in self.find_links(soup, url)[:10]:
                        queue.append((link, depth + 1))
            except Exception as e:
                logger.warning(f"Error extracting links from {url}: {e}")

            time.sleep(0.5)

        logger.info(f"Scraped {len(self.pages)} pages")
        return self.pages


class TextChunker:
    """Intelligently chunks text based on headers and token limits."""
    
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(ENCODER.encode(text))
    
    def chunk_text(self, text: str, headers: List[Dict] = None, 
                   metadata: Dict = None) -> List[Dict]:
        """Chunk text intelligently using headers and token limits."""
        chunks = []
        
        if not text or len(text.strip()) < 50:
            return chunks
        
        # If text is small enough, return as single chunk
        if self.count_tokens(text) <= self.chunk_size:
            chunks.append({
                'text': text,
                'metadata': metadata or {}
            })
            return chunks
        
        # Use headers to guide chunking if available
        if headers:
            # Split by headers
            header_positions = []
            for header in headers:
                # Find header position in text
                pos = text.find(header['text'])
                if pos != -1:
                    header_positions.append((pos, header))
            
            if header_positions:
                header_positions.sort(key=lambda x: x[0])
                
                # Create chunks between headers
                start = 0
                for i, (pos, header) in enumerate(header_positions):
                    if pos > start:
                        chunk_text = text[start:pos].strip()
                        if chunk_text and self.count_tokens(chunk_text) > 50:
                            chunks.append({
                                'text': chunk_text,
                                'metadata': {**(metadata or {}), 'section': header['text']}
                            })
                    start = pos
                
                # Add remaining text
                if start < len(text):
                    chunk_text = text[start:].strip()
                    if chunk_text and self.count_tokens(chunk_text) > 50:
                        chunks.append({
                            'text': chunk_text,
                            'metadata': metadata or {}
                        })
        
        # If header-based chunking didn't work or produced too large chunks,
        # fall back to token-based chunking
        if not chunks or any(self.count_tokens(c['text']) > self.chunk_size * 1.5 
                            for c in chunks):
            chunks = []
            sentences = re.split(r'(?<=[.!?])\s+', text)
            current_chunk = []
            current_tokens = 0
            
            for sentence in sentences:
                sent_tokens = self.count_tokens(sentence)
                
                if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                    # Save current chunk
                    chunk_text = ' '.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'metadata': metadata or {}
                    })
                    
                    # Start new chunk with overlap
                    overlap_sentences = current_chunk[-3:] if len(current_chunk) >= 3 else current_chunk
                    current_chunk = overlap_sentences + [sentence]
                    current_tokens = sum(self.count_tokens(s) for s in current_chunk)
                else:
                    current_chunk.append(sentence)
                    current_tokens += sent_tokens
            
            # Add final chunk
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'metadata': metadata or {}
                })
        
        # Ensure chunks are within size limits
        final_chunks = []
        for chunk in chunks:
            if self.count_tokens(chunk['text']) > self.chunk_size * 1.5:
                # Split oversized chunks
                sub_chunks = self._split_large_chunk(chunk['text'], chunk['metadata'])
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    def _split_large_chunk(self, text: str, metadata: Dict) -> List[Dict]:
        """Split a chunk that's too large."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sent_tokens = self.count_tokens(sentence)
            
            if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                chunks.append({
                    'text': ' '.join(current_chunk),
                    'metadata': metadata
                })
                current_chunk = [sentence]
                current_tokens = sent_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sent_tokens
        
        if current_chunk:
            chunks.append({
                'text': ' '.join(current_chunk),
                'metadata': metadata
            })
        
        return chunks


class ChromaDBIngester:
    """Handles ingestion into ChromaDB."""
    
    def __init__(self, db_path: str = "./chroma_db"):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="sunmarke_content",
            metadata={"hnsw:space": "cosine"}
        )
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = EMBEDDING_MODEL.encode(texts, show_progress_bar=True)
        return embeddings.tolist()
    
    def ingest_chunks(self, chunks: List[Dict]):
        """Ingest chunks into ChromaDB."""
        if not chunks:
            logger.warning("No chunks to ingest")
            return
        
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.generate_embeddings(texts)
        
        # Prepare metadata
        metadatas = []
        ids = []
        for i, chunk in enumerate(chunks):
            metadata = chunk.get('metadata', {})
            metadatas.append(metadata)
            ids.append(f"chunk_{i}_{hash(chunk['text']) % 100000}")
        
        # Add to collection
        logger.info(f"Adding {len(chunks)} chunks to ChromaDB...")
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        logger.info("Ingestion complete!")
    
    def get_collection_info(self):
        """Get information about the collection."""
        count = self.collection.count()
        logger.info(f"Collection contains {count} documents")
        return count


def load_html_from_disk(data_dir: str = "./data") -> List[Dict]:
    """Load HTML files from local directory as fallback."""
    pages = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        return pages
    
    logger.info(f"Checking for HTML files in {data_dir}...")
    html_files = list(data_path.glob("*.html")) + list(data_path.glob("*.htm"))
    
    if not html_files:
        return pages
    
    logger.info(f"Found {len(html_files)} HTML files, loading...")
    
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'lxml')
            
            # Extract text
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            
            main = soup.find("main") or soup.find("article") or soup.body
            if not main:
                continue
            
            text = " ".join(main.stripped_strings)
            
            if len(text) < 200:
                continue
            
            title = soup.title.string.strip() if soup.title else html_file.stem
            
            pages.append({
                "url": f"file://{html_file}",
                "title": title,
                "text": text,
                "headers": []
            })
            
            logger.info(f"Loaded: {html_file.name}")
        except Exception as e:
            logger.warning(f"Error loading {html_file}: {e}")
    
    return pages


def main():
    """Main ingestion pipeline."""
    logger.info("=" * 60)
    logger.info("Starting Sunmarke.com content ingestion")
    logger.info("=" * 60)
    
    # Step 1: Try to scrape website
    pages = []
    scraper = WebScraper(BASE_URL, max_depth=MAX_DEPTH, max_pages=MAX_PAGES)
    pages = scraper.crawl()
    scraper.client.close()
    
    # Step 1b: If scraping failed, try loading from local HTML files
    if not pages:
        logger.warning("Web scraping failed, trying to load HTML files from data/ directory...")
        pages = load_html_from_disk()
    
    if not pages:
        logger.error("No pages found. Exiting.")
        logger.error("=" * 60)
        logger.error("TROUBLESHOOTING:")
        logger.error("1. The website may be blocking automated requests")
        logger.error("2. Check your internet connection")
        logger.error("3. Try running the script again")
        logger.error("4. MANUAL CONTENT INGESTION:")
        logger.error("   - Create a 'data' directory in the project folder")
        logger.error("   - Save HTML pages from sunmarke.com to the data/ directory")
        logger.error("   - Run this script again - it will automatically load HTML files")
        logger.error("   - You can save pages using: File > Save Page As > Web Page, HTML Only")
        logger.error("=" * 60)
        return
    
    # Step 2: Chunk text
    logger.info("Chunking text...")
    chunker = TextChunker(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    all_chunks = []
    
    for page in pages:
        chunks = chunker.chunk_text(
            page['text'],
            headers=page.get('headers', []),
            metadata={
                'url': page['url'],
                'title': page['title']
            }
        )
        all_chunks.extend(chunks)
    
    # Close httpx client
    scraper.client.close()
    
    logger.info(f"Created {len(all_chunks)} chunks from {len(pages)} pages")
    
    # Step 3: Ingest into ChromaDB
    ingester = ChromaDBIngester()
    
    # Clear existing collection if needed (optional)
    # ingester.collection.delete()
    
    ingester.ingest_chunks(all_chunks)
    ingester.get_collection_info()
    
    logger.info("=" * 60)
    logger.info("Ingestion pipeline complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
