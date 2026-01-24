"""
Async LLM chains for Gemini, DeepSeek, and Kimi via OpenRouter.
Parallel querying with robust error handling.
"""

import os
import asyncio
import logging
from typing import Dict, List
from datetime import datetime

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Base LLM Chain
# ------------------------------------------------------------------
class LLMChain:
    def __init__(self, name: str, model_name: str):
        self.name = name
        self.model_name = model_name
        self.error_count = 0

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_headers={
                "HTTP-Referer": "http://localhost:8501",
                "X-Title": "Voice RAG App"
            }
        )

    async def generate(self, prompt: str) -> Dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful AI assistant. "
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


# ------------------------------------------------------------------
# Parallel LLM Manager
# ------------------------------------------------------------------
MODELS = {
    "gemini": "google/gemini-2.5-flash",
    "deepseek": "deepseek/deepseek-r1-0528:free", 
    "kimi": "moonshotai/kimi-k2-0905"
}

class ParallelLLMQuery:
    def __init__(self):
        self.chains = {}
        
        # Initialize each model with error handling
        for key, model_name in MODELS.items():
            try:
                chain = LLMChain(name=key.title(), model_name=model_name)
                self.chains[key] = chain
                logger.info(f"✅ {key.title()} chain initialized: {model_name}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {key}: {e}")
                continue
        
        logger.info(f"✅ {len(self.chains)} OpenRouter LLM chains initialized")

    async def query_all(self, prompt: str) -> Dict[str, Dict]:
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

    async def query_with_fallback(self, prompt: str) -> Dict:
        """Query models with fallback logic - try each model until one succeeds."""
        for name, chain in self.chains.items():
            try:
                result = await chain.generate(prompt)
                if not result.get("error", False):
                    logger.info(f"✅ Success with {name}")
                    return result
            except Exception as e:
                logger.warning(f"❌ {name} failed: {e}")
                continue
        
        # If all models fail, return error
        return {
            "model": "fallback",
            "response": "All models failed to respond. Please check your OpenRouter API key and try again.",
            "error": True,
            "timestamp": datetime.now().isoformat(),
        }

    def get_available_models(self) -> List[str]:
        return list(self.chains.keys())


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------
_parallel_query = None


def get_parallel_query() -> ParallelLLMQuery:
    global _parallel_query
    if _parallel_query is None:
        _parallel_query = ParallelLLMQuery()
    return _parallel_query
