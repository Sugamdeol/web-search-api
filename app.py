import re
import time
import asyncio
from typing import List, Optional, Dict, Any
from functools import lru_cache

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
from trafilatura.sitemaps import sitemap_search
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# ----------------------------
# Settings
# ----------------------------
class Settings(BaseSettings):
    USER_AGENT: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36"
    TIMEOUT: int = 15
    MAX_RESULTS: int = 20
    ALLOW_ORIGINS: List[str] = ["*"]  # Change in production
    RATE_LIMIT: str = "60/minute"     # Per IP
    ENABLE_SITEMAP: bool = True

settings = Settings()

# ----------------------------
# App Setup
# ----------------------------
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="LLM Web Search API", version="1.0.1")
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RateLimitExceeded)
def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(status_code=429, detail="Rate limit hit. Chill for a bit bro")

# ----------------------------
# Pydantic Models
# ----------------------------
class SearchParams(BaseModel):
    q: str = Field(..., description="The search query")
    num: int = Field(10, ge=1, le=settings.MAX_RESULTS)
    lang: str = Field("en")
    country: Optional[str] = Field(None, description="Country code like 'us' or 'in'")
    site: Optional[str] = Field(None, description="Restrict search to a specific site")
    safe: bool = Field(True, description="Enable safe search")
    tbs: Optional[str] = Field(None, description="Time filter like qdr:d (day), qdr:w (week), qdr:m (month)")
    dedupe: bool = Field(True)
    fetch_snippets: bool = Field(True, description="Fetch HTML title and meta description for each URL")
    parallel: int = Field(8, ge=1, le=16)

class ExtractParams(BaseModel):
    url: str
    include_html: bool = False
    with_metadata: bool = True
    fallback_readability: bool = True
    timeout: int = settings.TIMEOUT

class BatchExtractParams(BaseModel):
    urls: List[str]
    include_html: bool = False
    with_metadata: bool = True
    timeout: int = settings.TIMEOUT
    parallel: int = Field(8, ge=1, le=20)

class YTParams(BaseModel):
    video_id: str
    languages: List[str] = Field(default_factory=lambda: ["en", "en-US", "hi"])
    translate_to: Optional[str] = None

# ----------------------------
# Core Utility Functions
# ----------------------------
def json_dumps(obj: Any) -> bytes:
    return orjson.dumps(obj, option=orjson.OPT_INDENT_2)

HEADERS = {"User-Agent": settings.USER_AGENT}

def clean_text(t: Optional[str]) -> Optional[str]:
    if not t: return t
    return re.sub(r"\s+", " ", t).strip()

async def fetch_html(client: httpx.AsyncClient, url: str, timeout: int) -> Optional[str]:
    try:
        r = await client.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def extract_main_text(html: str, url: Optional[str] = None, fallback_readability: bool = True) -> Dict[str, Any]:
    try:
        data_str = trafilatura.extract(html, url=url, output_format='json')
        if data_str:
            return orjson.loads(data_str)
    except Exception:
        pass # Fallback

    if fallback_readability:
        try:
            from readability import Document
            doc = Document(html)
            title = clean_text(doc.short_title())
            content_html = doc.summary()
            soup = BeautifulSoup(content_html, "lxml")
            txt = clean_text(soup.get_text(separator=" "))
            return {"title": title, "text": txt, "url": url}
        except Exception:
            pass

    return {"title": None, "text": None, "url": url}

async def get_snippet(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else None
    desc = None
    if m := soup.find("meta", {"name": "description"}): desc = m.get("content")
    if not desc and (og := soup.find("meta", {"property": "og:description"})): desc = og.get("content")
    return {"title": clean_text(title), "description": clean_text(desc)}

def dedupe_urls(urls: List[str]) -> List[str]:
    seen, out = set(), []
    for u in urls:
        key = re.sub(r"#.*$", "", u.strip())
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out

# ----------------------------
# API Endpoints
# ----------------------------
@app.get("/")
def root():
    return {
        "name": "LLM Web Search API",
        "version": "1.0.1",
        "docs": "/docs",
        "endpoints": ["/search", "/extract", "/batch_extract", "/yt/subtitles", "/health"]
    }

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": time.time()}

@app.post("/search")
@limiter.limit(settings.RATE_LIMIT)
async def api_search(request: Request, params: SearchParams): # ✅ FIX: Added request: Request
    query = f"site:{params.site} {params.q}" if params.site else params.q
    
    # googlesearch is blocking, run in executor to not block the event loop
    loop = asyncio.get_event_loop()
    urls = await loop.run_in_executor(
        None, lambda: list(gsearch(query, num_results=params.num, lang=params.lang, stop=params.num))
    )

    if params.dedupe:
        urls = dedupe_urls(urls)

    out: List[Dict[str, Any]] = [{"url": u} for u in urls]

    if params.fetch_snippets and urls:
        async with httpx.AsyncClient(headers=HEADERS) as client:
            sem = asyncio.Semaphore(params.parallel)
            async def worker(u: str):
                async with sem:
                    html = await fetch_html(client, u, settings.TIMEOUT)
                    return await get_snippet(html) if html else {"title": None, "description": None}
            tasks = [worker(u) for u in urls]
            infos = await asyncio.gather(*tasks)

        for i, info in enumerate(infos):
            out[i].update(info)

    return orjson.loads(json_dumps({
        "query": params.q, "count": len(out), "results": out
    }))

@app.post("/extract")
@limiter.limit(settings.RATE_LIMIT)
async def api_extract(request: Request, p: ExtractParams): # ✅ FIX: Added request: Request
    async with httpx.AsyncClient(headers=HEADERS) as client:
        html = await fetch_html(client, p.url, p.timeout)
    if not html:
        raise HTTPException(status_code=422, detail="Could not fetch URL")

    data = extract_main_text(html, p.url, fallback_readability=p.fallback_readability)
    if not data.get("text"):
        raise HTTPException(status_code=422, detail="Could not extract clean text")

    res = {
        "url": p.url, "title": data.get("title"), "text": data.get("text"),
        "metadata": { "language": data.get("language"), "authors": data.get("authors"), "published": data.get("date") or data.get("published") } if p.with_metadata else None,
        "chars": len(data.get("text") or ""),
    }
    if p.include_html: res["html"] = html
    return orjson.loads(json_dumps(res))

@app.post("/batch_extract")
@limiter.limit(settings.RATE_LIMIT)
async def api_batch_extract(request: Request, p: BatchExtractParams): # ✅ FIX: Added request: Request
    async with httpx.AsyncClient(headers=HEADERS) as client:
        sem = asyncio.Semaphore(p.parallel)
        async def worker(u: str):
            async with sem:
                html = await fetch_html(client, u, p.timeout)
                if not html: return {"url": u, "ok": False, "error": "fetch_failed"}
                data = extract_main_text(html, u)
                if not data.get("text"): return {"url": u, "ok": False, "error": "extract_failed"}
                return { "url": u, "ok": True, "title": data.get("title"), "text": data.get("text"), "chars": len(data.get("text") or "")}
        results = await asyncio.gather(*[worker(u) for u in p.urls])
    return orjson.loads(json_dumps({"count": len(results), "items": results}))

def _yt_id_from_url(maybe_url: str) -> str:
    if m := re.search(r"(?:v=|/embed/|youtu\.be/|/v/|/e/|watch\?v=|\?v=|\&v=)([^#\&\?]{11})", maybe_url):
        return m.group(1)
    return maybe_url

@app.post("/yt/subtitles")
@limiter.limit(settings.RATE_LIMIT)
def yt_subtitles(request: Request, p: YTParams): # ✅ FIX: Added request: Request
    vid = _yt_id_from_url(p.video_id)
    try:
        if p.translate_to:
            tr = YouTubeTranscriptApi.list_transcripts(vid).find_transcript(p.languages).translate(p.translate_to)
            items = tr.fetch()
        else:
            items = YouTubeTranscriptApi.get_transcript(vid, languages=p.languages)
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube API error: {e}")

    full_text = " ".join([x["text"] for x in items if x.get("text")])
    return orjson.loads(json_dumps({
        "video_id": vid, "segments": items, "text": full_text, "chars": len(full_text)
    }))
