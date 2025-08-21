from flask import Flask, request, jsonify
from duckduckgo_search import DDGS

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "DuckDuckGo Search API running!"})

@app.route("/search", methods=["GET"])
def search_api():
    query = request.args.get("q")
    limit = int(request.args.get("limit", 10))

    if not query:
        return jsonify({"error": "Please provide a search query ?q=..."}), 400

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=limit):
                results.append({
                    "title": r.get("title"),
                    "link": r.get("href"),
                    "snippet": r.get("body")
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "query": query,
        "count": len(results),
        "results": results
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
