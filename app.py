from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests, hashlib, time
from bs4 import BeautifulSoup
import concurrent.futures

app = FastAPI(title="Free Search API", version="2.0")

# ------------------ Middlewares ------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ In-memory cache ------------------
cache = {}
CACHE_TTL = 120  # seconds


def cache_key(endpoint, params):
    raw = f"{endpoint}:{str(params)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached(endpoint, params):
    key = cache_key(endpoint, params)
    if key in cache:
        val, ts = cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
    return None


def set_cache(endpoint, params, data):
    key = cache_key(endpoint, params)
    cache[key] = (data, time.time())


# ------------------ Helpers ------------------
def fetch_json(url, params=None, headers=None):
    headers = headers or {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, params=params, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


# ------------------ Endpoints ------------------

@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=20, description="Number of results to return"),
    site: str = Query(None, description="Restrict results to a site"),
):
    """
    Search the web (DuckDuckGo as backend).
    """
    params = {"q": f"{q} site:{site}" if site else q, "format": "json", "no_redirect": 1}
    cached = get_cached("search", params)
    if cached:
        return cached

    url = "https://api.duckduckgo.com/"
    data = fetch_json(url, params=params)

    results = []
    for item in data.get("RelatedTopics", [])[:limit]:
        if "Text" in item and "FirstURL" in item:
            results.append({
                "title": item["Text"],
                "url": item["FirstURL"]
            })

    out = {"query": q, "count": len(results), "results": results}
    set_cache("search", params, out)
    return out


@app.get("/news")
def news(
    q: str = Query(..., description="News search query"),
    limit: int = Query(5, le=15)
):
    """
    Fetch latest news results.
    """
    params = {"q": q, "format": "json", "no_redirect": 1}
    cached = get_cached("news", params)
    if cached:
        return cached

    url = "https://api.duckduckgo.com/"
    data = fetch_json(url, params=params)

    results = []
    for item in data.get("RelatedTopics", [])[:limit]:
        if "Text" in item and "FirstURL" in item:
            results.append({
                "title": item["Text"],
                "url": item["FirstURL"]
            })

    out = {"query": q, "count": len(results), "results": results}
    set_cache("news", params, out)
    return out


@app.get("/images")
def images(
    q: str = Query(...),
    limit: int = Query(5, le=15)
):
    """
    Image search (via DuckDuckGo).
    """
    url = "https://duckduckgo.com/"
    params = {"q": q}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        token = requests.post(url, data=params, headers=headers).text
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get token")

    js_url = "https://duckduckgo.com/i.js"
    res = requests.get(js_url, params={"q": q, "o": "json"}, headers=headers)
    res.raise_for_status()
    data = res.json()

    results = []
    for item in data.get("results", [])[:limit]:
        results.append({
            "title": item.get("title"),
            "image": item.get("image"),
            "url": item.get("url"),
            "thumbnail": item.get("thumbnail")
        })

    return {"query": q, "count": len(results), "results": results}


@app.get("/suggest")
def suggest(
    q: str = Query(..., description="Get query suggestions")
):
    """
    Fetch search suggestions.
    """
    url = "https://duckduckgo.com/ac/"
    try:
        res = requests.get(url, params={"q": q})
        data = res.json()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch suggestions")

    suggestions = [s["phrase"] for s in data]
    return {"query": q, "suggestions": suggestions}


@app.get("/mix")
def mix_search(
    q: str = Query(..., description="Run search+news+images in parallel")
):
    """
    Run multiple searches in parallel.
    """
    out = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            "search": executor.submit(search, q, 5),
            "news": executor.submit(news, q, 3),
            "images": executor.submit(images, q, 3),
        }
        for key, f in futures.items():
            try:
                out[key] = f.result()
            except Exception as e:
                out[key] = {"error": str(e)}
    return out


@app.get("/fetch")
def fetch_content(
    url: str = Query(..., description="Full URL of the page to fetch content from"),
    text_only: bool = Query(True, description="If true, returns cleaned text only")
):
    """
    Fetch and parse content from a given URL.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; FastAPI-Scraper/2.0)"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")

    soup = BeautifulSoup(res.text, "html.parser")

    data = {
        "url": url,
        "title": soup.title.string if soup.title else None,
        "headings": [h.get_text(strip=True) for h in soup.find_all(["h1","h2","h3"])],
        "links": [{"text": a.get_text(strip=True), "href": a.get("href")} for a in soup.find_all("a", href=True)]
    }

    if text_only:
        for s in soup(["script", "style", "noscript"]):
            s.extract()
        data["text"] = soup.get_text(" ", strip=True)

    return data
