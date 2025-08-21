
# Free Search API 🚀

A free, fast, feature-rich API for search, news, images, suggestions, and webpage content fetching.  
Built with **FastAPI** and deployable on **Render**.

---

## Features
- 🔍 `/search` → Web search
- 📰 `/news` → News search
- 🖼️ `/images` → Image search
- 💡 `/suggest` → Search suggestions
- ⚡ `/mix` → Parallel search (search+news+images)
- 📑 `/fetch` → Fetch and parse webpage contents (title, headings, links, clean text)

---

## Run Locally
```bash
pip install -r requirements.txt
uvicorn app:app --reload
````

Visit: `http://127.0.0.1:8000/docs`

---

## Deploy on Render

1. Push code to GitHub
2. On Render → New Web Service → Connect repo
3. Done! Your API is live 🎉

---

## Example Requests

**Search**

```
GET /search?q=ai+tools&limit=5
```

**News**

```
GET /news?q=india
```

**Images**

```
GET /images?q=cat&limit=3
```

**Suggestions**

```
GET /suggest?q=machine
```

**Mix**

```
GET /mix?q=cricket
```

**Fetch Content**

```
GET /fetch?url=https://example.com&text_only=true
```

```


