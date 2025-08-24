import re
import time
import asyncio
from typing import List, Optional, Dict, Any

import orjson
import httpx
from fastapi import FastAPI, Query, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from googlesearch import search as gsearch
import trafilatura
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# ----------------------------
# Settings
# ----------------------------
class Settings(BaseSettings):
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    TIMEOUT: int = 15
    MAX_RESULTS: int = 20
    RATE_LIMIT: str = "60/minute"

settings = Settings()

# ----------------------------
# App & Middleware Setup
# ----------------------------
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="LLM Web Search API", version="1.0.3-stable")
app.state.limiter = limiter

# ✅ FIX: CORS Middleware for browser access from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RateLimitExceeded)
def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")

# ----------------------------
# Pydantic Models for Request Bodies
# ----------------------------
class SearchParams(BaseModel):
    q: str = Field(..., description="The search query")
    num: int = Field(10, ge=1, le=settings.MAX_RESULTS)
    fetch_snippets: bool = Field(True, description="Fetch HTML title and meta description for each URL")

class ExtractParams(BaseModel):
    url: str

class BatchExtractParams(BaseModel):
    urls: List[str]

class YTParams(BaseModel):
    video_id: str
    languages: List[str] = Field(default_factory=lambda: ["en", "en-US"])

# ----------------------------
# Helper Functions
# ----------------------------
HEADERS = {"User-Agent": settings.USER_AGENT}

async def fetch_html(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url, headers=HEADERS, timeout=settings.TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def extract_main_text(html: str, url: str) -> Dict[str, Any]:
    try:
        # Trafilatura is best for clean text extraction
        data_str = trafilatura.extract(html, url=url, output_format='json', include_comments=False)
        if data_str:
            return orjson.loads(data_str)
    except Exception:
        pass # Fallback to BeautifulSoup
    
    # Fallback if trafilatura fails
    soup = BeautifulSoup(html, "lxml")
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    text = " ".join(t.strip() for t in soup.stripped_strings)
    title = soup.title.string.strip() if soup.title else "No title found"
    return {"text": text, "title": title, "url": url}

async def get_snippet(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else None
    desc = None
    if m := soup.find("meta", {"name": "description"}): desc = m.get("content", "").strip()
    return {"title": title, "description": desc}

def _yt_id_from_url(url_or_id: str) -> str:
    if m := re.search(r"(?:v=|/embed/|youtu\.be/|/v/|/e/|watch\?v=|\?v=|\&v=)([^#\&\?]{11})", url_or_id):
        return m.group(1)
    return url_or_id

# ----------------------------
# API Endpoints
# ----------------------------

@app.get("/")
def root():
    return {"message": "Welcome to the Stable Web Search API. Visit /docs for documentation."}

@app.post("/search")
@limiter.limit(settings.RATE_LIMIT)
async def api_search(request: Request, params: SearchParams):
    # ✅ FIX: Full error handling to prevent 500 crashes
    try:
        loop = asyncio.get_event_loop()
        urls = await loop.run_in_executor(
            None, 
            lambda: list(gsearch(params.q, num_results=params.num, lang='en', user_agent=settings.USER_AGENT))
        )

        if not urls:
            return {"query": params.q, "count": 0, "results": [], "warning": "No results found or request was blocked by Google."}

        results = [{"url": u} for u in urls]
        
        if params.fetch_snippets:
            async with httpx.AsyncClient() as client:
                tasks = [fetch_html(client, res["url"]) for res in results]
                html_contents = await asyncio.gather(*tasks)
                
                for i, html in enumerate(html_contents):
                    if html:
                        snippet = await get_snippet(html)
                        results[i].update(snippet)

        return {"query": params.q, "count": len(results), "results": results}

    except Exception as e:
        print(f"!!! SERVER-SIDE ERROR in /search: {e}") # This will appear in your Render logs
        raise HTTPException(
            status_code=503, # Service Unavailable
            detail=f"Failed to fetch search results. The server is likely blocked by Google. Please try again later. Error: {str(e)}"
        )

@app.post("/extract")
@limiter.limit(settings.RATE_LIMIT)
async def api_extract(request: Request, params: ExtractParams):
    try:
        async with httpx.AsyncClient() as client:
            html = await fetch_html(client, params.url)
        
        if not html:
            raise HTTPException(status_code=422, detail="Could not fetch content from URL. It may be down or blocking requests.")
        
        data = extract_main_text(html, params.url)
        return data

    except Exception as e:
        print(f"!!! SERVER-SIDE ERROR in /extract: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract content. Error: {str(e)}")

@app.post("/yt/subtitles")
@limiter.limit(settings.RATE_LIMIT)
def yt_subtitles(request: Request, p: YTParams):
    try:
        vid = _yt_id_from_url(p.video_id)
        transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
        transcript = transcript_list.find_transcript(p.languages)
        items = transcript.fetch()
        full_text = " ".join([item["text"] for item in items])
        return {"video_id": vid, "language": transcript.language_code, "text": full_text, "segments": items}
        
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise HTTPException(status_code=404, detail=f"Could not find subtitles for this video. Reason: {str(e)}")
    except Exception as e:
        print(f"!!! SERVER-SIDE ERROR in /yt/subtitles: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred. Error: {str(e)}")
