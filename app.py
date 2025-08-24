import re
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
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Settings
class Settings(BaseSettings):
    TIMEOUT: int = 15
    MAX_RESULTS: int = 20
    RATE_LIMIT: str = "60/minute"

settings = Settings()

# App & Middleware
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="LLM Web Search API", version="1.0.6-stable")
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RateLimitExceeded)
def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(status_code=429, detail="Rate limit exceeded.")

# Pydantic Models
class SearchParams(BaseModel):
    q: str = Field(..., description="The search query")
    num: int = Field(10, ge=1, le=settings.MAX_RESULTS)
    fetch_snippets: bool = Field(True)

class ExtractParams(BaseModel):
    url: str

class YTParams(BaseModel):
    video_id: str
    languages: List[str] = Field(default_factory=lambda: ["en", "en-US"])

# Helper Functions
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}
async def fetch_html(client: httpx.AsyncClient, url: str):
    try:
        r = await client.get(url, headers=HEADERS, timeout=settings.TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception: return None

async def get_snippet(html: str):
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else "No Title Found"
    desc = ""
    if m := soup.find("meta", {"name": "description"}): desc = m.get("content", "").strip()
    return {"title": title, "description": desc}

def _yt_id_from_url(url_or_id: str):
    if m := re.search(r"(?:v=|/embed/|youtu\.be/|/v/|/e/|watch\?v=|\?v=|\&v=)([^#\&\?]{11})", url_or_id):
        return m.group(1)
    return url_or_id

# API Endpoints
@app.get("/")
def root():
    return {"message": "API is running. Visit /docs for documentation."}

@app.post("/search")
@limiter.limit(settings.RATE_LIMIT)
async def api_search(request: Request, params: SearchParams):
    try:
        loop = asyncio.get_event_loop()
        # ✅ FIX: Removed the unsupported 'stop' argument. 'num_results' is the correct one.
        urls = await loop.run_in_executor(
            None,
            lambda: list(gsearch(params.q, num_results=params.num, lang='en'))
        )
        if not urls: return {"query": params.q, "count": 0, "results": [], "warning": "No results found or request was blocked by Google."}
        
        results = [{"url": u} for u in urls]
        if params.fetch_snippets:
            async with httpx.AsyncClient() as client:
                tasks = [fetch_html(client, res["url"]) for res in results]
                html_contents = await asyncio.gather(*tasks)
                for i, html in enumerate(html_contents):
                    if html: results[i].update(await get_snippet(html))
        
        return {"query": params.q, "count": len(results), "results": results}
    except Exception as e:
        print(f"ERROR in /search: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to fetch search results. Server might be blocked. Error: {str(e)}")

@app.post("/extract")
@limiter.limit(settings.RATE_LIMIT)
async def api_extract(request: Request, params: ExtractParams):
    try:
        async with httpx.AsyncClient() as client: html = await fetch_html(client, params.url)
        if not html: raise HTTPException(status_code=422, detail="Could not fetch content from URL.")
        data_str = trafilatura.extract(html, url=params.url, output_format='json')
        return orjson.loads(data_str) if data_str else {"text": "Could not extract main content.", "url": params.url}
    except Exception as e:
        print(f"ERROR in /extract: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract content. Error: {str(e)}")

@app.post("/yt/subtitles")
@limiter.limit(settings.RATE_LIMIT)
def yt_subtitles(request: Request, p: YTParams):
    try:
        vid = _yt_id_from_url(p.video_id)
        # This code is correct, the problem is an old library version on Render
        transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
        transcript = transcript_list.find_transcript(p.languages)
        items = transcript.fetch()
        full_text = " ".join([item["text"].replace('\n', ' ') for item in items])
        return {"video_id": vid, "language_code": transcript.language_code, "text": full_text, "segments": items}
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise HTTPException(status_code=404, detail=f"Could not find subtitles. Reason: {str(e)}")
    except Exception as e:
        print(f"ERROR in /yt/subtitles: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred. Error: {str(e)}")
