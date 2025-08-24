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
    ALLOW_ORIGINS: List[str] = ["*"]  # change in prod
    RATE_LIMIT: str = "60/minute"     # per IP
    ENABLE_SITEMAP: bool = True

settings = Settings()

# ----------------------------
# App
# ----------------------------
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="LLM Web Search API", version="1.0.0")
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
# Models
# ----------------------------
class SearchParams(BaseModel):
    q: str = Field(..., description="query")
    num: int = Field(10, ge=1, le=settings.MAX_RESULTS)
    lang: str = Field("en")
    country: Optional[str] = Field(None, description="gl param like us in")
    site: Optional[str] = Field(None, description="restrict to site")
    safe: bool = Field(True, description="safe search hint")
    tbs: Optional[str] = Field(None, description="time filter like qdr:d, qdr:w, qdr:m")
    dedupe: bool = Field(True)
    fetch_snippets: bool = Field(True, description="fetch each URL HTML title and meta description")
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
    translate_to: Optional[str] = None  # like "en" or "hi"

# ----------------------------
# Utils
# ----------------------------
def json_dumps(obj: Any) -> bytes:
    return orjson.dumps(obj, option=orjson.OPT_INDENT_2)

HEADERS = {"User-Agent": settings.USER_AGENT}

def clean_text(t: Optional[str]) -> Optional[str]:
    if not t:
        return t
    t = re.sub(r"\s+", " ", t).strip()
    return t

@lru_cache(maxsize=2048)
def _cache_key(url: str) -> str:
    return url

async def fetch_html(client: httpx.AsyncClient, url: str, timeout: int) -> Optional[str]:
    try:
        r = await client.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        if r.status_code >= 400:
            return None
        return r.text
    except Exception:
        return None

def extract_main_text(html: str, url: Optional[str] = None, fallback_readability: bool = True) -> Dict[str, Any]:
    # Try trafilatura first
    downloaded = html
    text = trafilatura.extract(downloaded, include_links=False, include_images=False, url=url, with_metadata=True)
    if text:
        data = trafilatura.extract(downloaded, include_formatting=False, url=url, output="json")
        if data:
            return orjson.loads(data)

    # Fallback: readability
    if fallback_readability:
        try:
            from readability import Document
            doc = Document(html)
            title = clean_text(doc.short_title())
            content_html = doc.summary()
            soup = BeautifulSoup(content_html, "lxml")
            txt = clean_text(soup.get_text(separator=" "))
            return {
                "title": title,
                "text": txt,
                "url": url,
                "language": None,
                "authors": [],
                "published": None
            }
        except Exception:
            pass

    # Nothing worked
    return {"title": None, "text": None, "url": url}

async def get_snippet(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else None
    desc = None
    m = soup.find("meta", {"name": "description"})
    if m and m.get("content"):
        desc = m["content"].strip()
    og = soup.find("meta", {"property": "og:description"})
    if not desc and og and og.get("content"):
        desc = og["content"].strip()
    return {"title": clean_text(title), "description": clean_text(desc)}

def add_site_filter(q: str, site: Optional[str]) -> str:
    if site:
        return f"site:{site} {q}"
    return q

def add_time_filter(q: str, tbs: Optional[str]) -> str:
    # googlesearch-python does not expose tbs directly
    # we keep q same and let client add context words if needed
    return q

def dedupe_urls(urls: List[str]) -> List[str]:
    seen = set()
    out = []
    for u in urls:
        key = re.sub(r"#.*$", "", u.strip())
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out

# ----------------------------
# Endpoints
# ----------------------------
@app.get("/health")
def health():
    return {"ok": True, "ts": time.time()}

@app.post("/search")
@limiter.limit(settings.RATE_LIMIT)
async def api_search(params: SearchParams):
    q = add_time_filter(add_site_filter(params.q, params.site), params.tbs)

    # googlesearch-python returns URLs only
    urls = list(gsearch(q, num_results=params.num, lang=params.lang, region=params.country or ""))

    if params.dedupe:
        urls = dedupe_urls(urls)

    out: List[Dict[str, Any]] = [{"url": u} for u in urls]

    if params.fetch_snippets and urls:
        async with httpx.AsyncClient(headers=HEADERS) as client:
            sem = asyncio.Semaphore(params.parallel)
            async def worker(u: str):
                async with sem:
                    html = await fetch_html(client, u, settings.TIMEOUT)
                    if not html:
                        return {"title": None, "description": None}
                    return await get_snippet(html)
            tasks = [worker(u) for u in urls]
            infos = await asyncio.gather(*tasks, return_exceptions=True)

        for i, info in enumerate(infos):
            if isinstance(info, Exception):
                info = {"title": None, "description": None}
            out[i].update(info)

    # add sitemap hints for LLM crawl planning
    if settings.ENABLE_SITEMAP:
        for item in out:
            try:
                dom = re.sub(r"^https?://", "", item["url"]).split("/")[0]
                sm = sitemap_search("https://" + dom)
                if sm:
                    item["sitemap"] = sm[:3]
            except Exception:
                item["sitemap"] = None

    return orjson.loads(json_dumps({
        "query": params.q,
        "lang": params.lang,
        "country": params.country,
        "count": len(out),
        "results": out
    }))

@app.post("/extract")
@limiter.limit(settings.RATE_LIMIT)
async def api_extract(p: ExtractParams):
    async with httpx.AsyncClient(headers=HEADERS) as client:
        html = await fetch_html(client, p.url, p.timeout)
    if not html:
        raise HTTPException(status_code=422, detail="Could not fetch URL")

    data = extract_main_text(html, p.url, fallback_readability=p.fallback_readability)
    if not data.get("text"):
        raise HTTPException(status_code=422, detail="Could not extract clean text")

    res = {
        "url": p.url,
        "title": data.get("title"),
        "text": data.get("text"),
        "metadata": {
            "language": data.get("language"),
            "authors": data.get("authors"),
            "published": data.get("date") or data.get("published")
        } if p.with_metadata else None,
        "chars": len(data.get("text") or ""),
    }
    if p.include_html:
        res["html"] = html
    return orjson.loads(json_dumps(res))

@app.post("/batch_extract")
@limiter.limit(settings.RATE_LIMIT)
async def api_batch_extract(p: BatchExtractParams):
    async with httpx.AsyncClient(headers=HEADERS) as client:
        sem = asyncio.Semaphore(p.parallel)
        async def worker(u: str):
            async with sem:
                html = await fetch_html(client, u, p.timeout)
                if not html:
                    return {"url": u, "ok": False, "error": "fetch_failed"}
                data = extract_main_text(html, u)
                if not data.get("text"):
                    return {"url": u, "ok": False, "error": "extract_failed"}
                return {
                    "url": u, "ok": True,
                    "title": data.get("title"),
                    "text": data.get("text"),
                    "chars": len(data.get("text") or "")
                }
        results = await asyncio.gather(*[worker(u) for u in p.urls])
    return orjson.loads(json_dumps({"count": len(results), "items": results}))

def _yt_id_from_url(maybe_url: str) -> str:
    # handle full URL or id
    m = re.search(r"(?:v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{6,})", maybe_url)
    return m.group(1) if m else maybe_url

@app.post("/yt/subtitles")
@limiter.limit(settings.RATE_LIMIT)
def yt_subtitles(p: YTParams):
    vid = _yt_id_from_url(p.video_id)
    try:
        if p.translate_to:
            transcripts = YouTubeTranscriptApi.list_transcripts(vid)
            tr = transcripts.find_transcript(p.languages)
            tr = tr.translate(p.translate_to)
            items = tr.fetch()
        else:
            items = YouTubeTranscriptApi.get_transcript(vid, languages=p.languages)
    except TranscriptsDisabled:
        raise HTTPException(status_code=403, detail="Subtitles disabled")
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No transcript found")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YT error: {e}")

    # pack for LLMs
    full_text = " ".join([x["text"] for x in items if x.get("text")])
    return orjson.loads(json_dumps({
        "video_id": vid,
        "segments": items,
        "text": full_text,
        "chars": len(full_text)
    }))

# Root helper
@app.get("/")
def root():
    return {
        "name": "LLM Web Search API",
        "version": "1.0.0",
        "endpoints": ["/search", "/extract", "/batch_extract", "/yt/subtitles", "/health"]
    }
