# app.py
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from typing import Optional
from duckduckgo_search import DDGS
import time
import re
from urllib.parse import urlparse
from collections import defaultdict, deque
from cachetools import TTLCache
import asyncio

APP_NAME = "TurboDuck Search API"

app = FastAPI(title=APP_NAME, version="1.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# gzip compression
app.add_middleware(GZipMiddleware, minimum_size=500)

# simple in-memory TTL cache
CACHE_TTL_SECONDS = int(60 * 30)  # 30 min
CACHE_MAXSIZE = 10_000
cache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)

# basic token bucket rate limit per IP
RATE_LIMIT = 60  # requests
RATE_WINDOW = 60  # seconds
_buckets = defaultdict(lambda: deque())

# ---------- helpers ----------

def canon_url(u: str) -> str:
    try:
        p = urlparse(u)
        clean = f"{p.scheme}://{p.netloc}{p.path}"
        if clean.endswith('/'):
            clean = clean[:-1]
        return clean
    except Exception:
        return u

def dedupe(items, key=lambda x: x):
    seen = set()
    out = []
    for it in items:
        k = key(it)
        if k and k not in seen:
            out.append(it)
            seen.add(k)
    return out

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def make_cache_key(route: str, params: dict):
    parts = [route]
    for k in sorted(params.keys()):
        parts.append(f"{k}={params[k]}")
    return "|".join(parts)

async def rate_limiter(request: Request):
    ip = request.client.host if request.client else "0.0.0.0"
    now = time.time()
    q = _buckets[ip]
    # purge old
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, detail="Too many requests, slow down")
    q.append(now)

def parse_time_range(tr: Optional[str]):
    if not tr:
        return None
    m = re.fullmatch(r"(\d+)([dwmy])", tr.strip())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    days = {"d": 1, "w": 7, "m": 30, "y": 365}[unit] * n
    return days

class SearchResponse(BaseModel):
    query: str
    count: int
    page: int
    per_page: int
    results: list
    took_ms: int
    source: str = "duckduckgo"

@app.middleware("http")
async def _global_rate_limit(request: Request, call_next):
    try:
        await rate_limiter(request)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)
    return await call_next(request)

@app.get("/")
async def root():
    return {
        "name": APP_NAME,
        "version": "1.1.0",
        "routes": [
            "/search", "/news", "/images", "/videos", "/suggest", "/mix",
        ],
        "docs": "/docs"
    }

# ---------------- core search endpoints ----------------

@app.get("/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=1),
                 limit: int = Query(10, ge=1, le=50),
                 page: int = Query(1, ge=1),
                 region: Optional[str] = Query(None, description="like 'us-en' or 'in-en'"),
                 safesearch: Optional[str] = Query("moderate", description="off, moderate, strict"),
                 site: Optional[str] = Query(None, description="only this domain"),
                 exclude_site: Optional[str] = Query(None, description="block this domain")):
    t0 = time.time()
    per_page = limit
    params = {
        "q": q, "limit": limit, "page": page,
        "region": region or "", "safesearch": safesearch or "",
        "site": site or "", "exclude_site": exclude_site or ""
    }
    key = make_cache_key("/search", params)
    if key in cache:
        data = cache[key]
        data["took_ms"] = int((time.time() - t0) * 1000)
        return data

    query = q
    if site:
        query += f" site:{site}"
    if exclude_site:
        query += f" -site:{exclude_site}"

    offset = (page - 1) * per_page
    raw = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, region=region, safesearch=safesearch, max_results=offset + per_page):
            raw.append({
                "title": r.get("title"),
                "url": r.get("href"),
                "snippet": r.get("body"),
                "source": urlparse(r.get("href", "")).netloc if r.get("href") else None
            })

    raw = dedupe(raw, key=lambda x: canon_url(x.get("url")))
    page_items = raw[offset: offset + per_page]

    resp = {
        "query": q,
        "count": len(page_items),
        "page": page,
        "per_page": per_page,
        "results": page_items,
        "took_ms": int((time.time() - t0) * 1000),
        "source": "duckduckgo"
    }
    cache[key] = resp
    return resp

@app.get("/news", response_model=SearchResponse)
async def news(q: str = Query(..., min_length=1),
               limit: int = Query(10, ge=1, le=50),
               page: int = Query(1, ge=1),
               region: Optional[str] = None,
               safesearch: Optional[str] = "moderate",
               freshness: Optional[str] = Query(None, description="like 7d, 30d, 1y")):
    t0 = time.time()
    params = {"q": q, "limit": limit, "page": page, "region": region or "", "freshness": freshness or ""}
    key = make_cache_key("/news", params)
    if key in cache:
        data = cache[key]
        data["took_ms"] = int((time.time() - t0) * 1000)
        return data

    per_page = limit
    offset = (page - 1) * per_page
    timelimit = parse_time_range(freshness)

    raw = []
    with DDGS() as ddgs:
        for r in ddgs.news(q, region=region, safesearch=safesearch, max_results=offset + per_page, timelimit=timelimit):
            raw.append({
                "title": r.get("title"),
                "url": r.get("url"),
                "published": r.get("date"),
                "source": r.get("source")
            })

    raw = dedupe(raw, key=lambda x: canon_url(x.get("url")))
    page_items = raw[offset: offset + per_page]

    resp = {
        "query": q,
        "count": len(page_items),
        "page": page,
        "per_page": per_page,
        "results": page_items,
        "took_ms": int((time.time() - t0) * 1000),
        "source": "duckduckgo"
    }
    cache[key] = resp
    return resp

@app.get("/images", response_model=SearchResponse)
async def images(q: str = Query(..., min_length=1),
                 limit: int = Query(10, ge=1, le=50),
                 page: int = Query(1, ge=1),
                 region: Optional[str] = None,
                 safesearch: Optional[str] = "moderate",
                 size: Optional[str] = Query(None, description="Small, Medium, Large, Wallpaper"),
                 color: Optional[str] = Query(None, description="color filter like red, blue, mono")):
    t0 = time.time()
    params = {"q": q, "limit": limit, "page": page, "region": region or "", "size": size or "", "color": color or ""}
    key = make_cache_key("/images", params)
    if key in cache:
        data = cache[key]
        data["took_ms"] = int((time.time() - t0) * 1000)
        return data

    per_page = limit
    offset = (page - 1) * per_page

    raw = []
    with DDGS() as ddgs:
        for r in ddgs.images(q, region=region, safesearch=safesearch, size=size, color=color, max_results=offset + per_page):
            raw.append({
                "title": r.get("title"),
                "image": r.get("image"),
                "thumbnail": r.get("thumbnail"),
                "source": r.get("source")
            })

    raw = dedupe(raw, key=lambda x: x.get("image"))
    page_items = raw[offset: offset + per_page]

    resp = {
        "query": q,
        "count": len(page_items),
        "page": page,
        "per_page": per_page,
        "results": page_items,
        "took_ms": int((time.time() - t0) * 1000),
        "source": "duckduckgo"
    }
    cache[key] = resp
    return resp

@app.get("/videos", response_model=SearchResponse)
async def videos(q: str = Query(..., min_length=1),
                 limit: int = Query(10, ge=1, le=50),
                 page: int = Query(1, ge=1),
                 region: Optional[str] = None,
                 safesearch: Optional[str] = "moderate"):
    t0 = time.time()
    params = {"q": q, "limit": limit, "page": page, "region": region or ""}
    key = make_cache_key("/videos", params)
    if key in cache:
        data = cache[key]
        data["took_ms"] = int((time.time() - t0) * 1000)
        return data

    per_page = limit
    offset = (page - 1) * per_page

    raw = []
    with DDGS() as ddgs:
        for r in ddgs.videos(q, region=region, safesearch=safesearch, max_results=offset + per_page):
            raw.append({
                "title": r.get("title"),
                "url": r.get("content"),
                "duration": r.get("duration"),
                "publisher": r.get("publisher"),
            })

    raw = dedupe(raw, key=lambda x: canon_url(x.get("url")))
    page_items = raw[offset: offset + per_page]

    resp = {
        "query": q,
        "count": len(page_items),
        "page": page,
        "per_page": per_page,
        "results": page_items,
        "took_ms": int((time.time() - t0) * 1000),
        "source": "duckduckgo"
    }
    cache[key] = resp
    return resp

@app.get("/suggest")
async def suggest(q: str = Query(..., min_length=1), region: Optional[str] = None):
    key = make_cache_key("/suggest", {"q": q, "region": region or ""})
    if key in cache:
        return cache[key]
    out = []
    with DDGS() as ddgs:
        for s in ddgs.suggestions(q, region=region):
            val = s.get("phrase") or s.get("value") or s.get("phrase")
            if val:
                out.append(val)
    data = {"query": q, "suggestions": out[:20]}
    cache[key] = data
    return data

@app.get("/mix")
async def mix(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=20)):
    t0 = time.time()
    async def _run(func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    def s_text():
        with DDGS() as ddgs:
            return [
                {"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body")}
                for r in ddgs.text(q, max_results=limit)
            ]

    def s_news():
        with DDGS() as ddgs:
            return [
                {"title": r.get("title"), "url": r.get("url"), "published": r.get("date"), "source": r.get("source")}
                for r in ddgs.news(q, max_results=limit)
            ]

    def s_images():
        with DDGS() as ddgs:
            return [
                {"title": r.get("title"), "image": r.get("image"), "thumbnail": r.get("thumbnail")}
                for r in ddgs.images(q, max_results=limit)
            ]

    text, news_res, images_res = await asyncio.gather(_run(s_text), _run(s_news), _run(s_images))

    return {
        "query": q,
        "took_ms": int((time.time() - t0) * 1000),
        "web": text,
        "news": news_res,
        "images": images_res,
    }
