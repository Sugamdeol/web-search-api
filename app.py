from flask import Flask, request, jsonify
from duckduckgo_search import DDGS

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "DuckDuckGo Search API running!",
        "routes": ["/search", "/news", "/images", "/videos"]
    })

# --- Normal Web Search ---
@app.route("/search", methods=["GET"])
def search_api():
    query = request.args.get("q")
    limit = int(request.args.get("limit", 10))
    if not query:
        return jsonify({"error": "Please provide a query ?q=..."}), 400

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=limit):
            results.append({
                "title": r.get("title"),
                "link": r.get("href"),
                "snippet": r.get("body")
            })
    return jsonify({"query": query, "count": len(results), "results": results})

# --- News Search ---
@app.route("/news", methods=["GET"])
def news_api():
    query = request.args.get("q")
    limit = int(request.args.get("limit", 10))
    if not query:
        return jsonify({"error": "Please provide a query ?q=..."}), 400

    results = []
    with DDGS() as ddgs:
        for r in ddgs.news(query, max_results=limit):
            results.append({
                "title": r.get("title"),
                "link": r.get("url"),
                "published": r.get("date"),
                "source": r.get("source")
            })
    return jsonify({"query": query, "count": len(results), "results": results})

# --- Image Search ---
@app.route("/images", methods=["GET"])
def images_api():
    query = request.args.get("q")
    limit = int(request.args.get("limit", 10))
    if not query:
        return jsonify({"error": "Please provide a query ?q=..."}), 400

    results = []
    with DDGS() as ddgs:
        for r in ddgs.images(query, max_results=limit):
            results.append({
                "title": r.get("title"),
                "image": r.get("image"),
                "thumbnail": r.get("thumbnail"),
                "source": r.get("source")
            })
    return jsonify({"query": query, "count": len(results), "results": results})

# --- Video Search ---
@app.route("/videos", methods=["GET"])
def videos_api():
    query = request.args.get("q")
    limit = int(request.args.get("limit", 10))
    if not query:
        return jsonify({"error": "Please provide a query ?q=..."}), 400

    results = []
    with DDGS() as ddgs:
        for r in ddgs.videos(query, max_results=limit):
            results.append({
                "title": r.get("title"),
                "link": r.get("content"),
                "duration": r.get("duration"),
                "source": r.get("publisher")
            })
    return jsonify({"query": query, "count": len(results), "results": results})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
