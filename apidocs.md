

# 📖 Search API Documentation

## 🔗 Base URL

```
https://web-search-api-qd7c.onrender.com/
```

---

## 🟢 Health Check

**Endpoint:**

```
GET /
```

**Response:**

```json
{
  "status": "ok",
  "message": "DuckDuckGo Search API running!"
}
```

---

## 🔍 Web Search

**Endpoint:**

```
GET /search
```

**Query Parameters:**

| Param          | Type   | Default    | Description                         |
| -------------- | ------ | ---------- | ----------------------------------- |
| `q`            | string | required   | Search query                        |
| `limit`        | int    | 10         | Number of results                   |
| `region`       | string | "wt-wt"    | Region (e.g. `in-en`, `us-en`)      |
| `safesearch`   | string | "moderate" | `off`, `moderate`, `strict`         |
| `include_site` | string | null       | Only include results from this site |
| `exclude_site` | string | null       | Exclude results from this site      |

**Example:**

```
/search?q=ai+tools&limit=5&region=in-en&exclude_site=reddit.com
```

**Response:**

```json
{
  "query": "ai tools",
  "count": 5,
  "results": [
    {
      "title": "Top 10 Free AI Tools",
      "link": "https://example.com",
      "snippet": "Here are the best free AI tools..."
    }
  ]
}
```

---

## 📰 News Search

**Endpoint:**

```
GET /news
```

**Query Parameters:**

| Param        | Type   | Default    | Description               |
| ------------ | ------ | ---------- | ------------------------- |
| `q`          | string | required   | News search query         |
| `limit`      | int    | 10         | Number of results         |
| `region`     | string | "wt-wt"    | News region               |
| `safesearch` | string | "moderate" | Safe search level         |
| `timelimit`  | string | null       | Freshness (`d`, `w`, `m`) |

**Example:**

```
/news?q=india+elections&timelimit=d
```

**Response:**

```json
{
  "query": "india elections",
  "count": 2,
  "results": [
    {
      "title": "Election Results Announced",
      "link": "https://news-site.com/article",
      "snippet": "The election results were announced today...",
      "date": "2025-08-20T10:00:00Z",
      "source": "BBC News"
    }
  ]
}
```

---

## 🖼️ Image Search

**Endpoint:**

```
GET /images
```

**Query Parameters:**

| Param   | Type   | Default  | Description                               |
| ------- | ------ | -------- | ----------------------------------------- |
| `q`     | string | required | Image search query                        |
| `limit` | int    | 10       | Number of results                         |
| `size`  | string | null     | `small`, `medium`, `large`, `wallpaper`   |
| `color` | string | null     | `color`, `monochrome`, `red`, `blue`, etc |
| `type`  | string | null     | `photo`, `clipart`, `gif`, `transparent`  |

**Example:**

```
/images?q=dog&limit=3&size=large&color=red
```

**Response:**

```json
{
  "query": "dog",
  "count": 3,
  "results": [
    {
      "title": "Cute Red Dog",
      "image": "https://img.example.com/dog1.jpg",
      "thumbnail": "https://img.example.com/thumb_dog1.jpg",
      "source": "https://example.com"
    }
  ]
}
```

---

## 🎥 Video Search

**Endpoint:**

```
GET /videos
```

**Query Parameters:**

| Param    | Type   | Default  | Description        |
| -------- | ------ | -------- | ------------------ |
| `q`      | string | required | Video search query |
| `limit`  | int    | 10       | Number of results  |
| `region` | string | "wt-wt"  | Region             |

**Example:**

```
/videos?q=python+tutorial&limit=2
```

**Response:**

```json
{
  "query": "python tutorial",
  "count": 2,
  "results": [
    {
      "title": "Python Basics Tutorial",
      "link": "https://youtube.com/watch?v=xyz",
      "source": "YouTube",
      "snippet": "Learn Python basics in this video."
    }
  ]
}
```

---

## ✨ Suggestions (Autocomplete)

**Endpoint:**

```
GET /suggest
```

**Query Parameters:**

| Param | Type   | Description                   |
| ----- | ------ | ----------------------------- |
| `q`   | string | Search prefix for suggestions |

**Example:**

```
/suggest?q=python
```

**Response:**

```json
{
  "query": "python",
  "suggestions": [
    "python tutorial",
    "python for beginners",
    "python vs java"
  ]
}
```

---

## ⚡ Mix Search (Parallel)

**Endpoint:**

```
GET /mix
```

**Query Parameters:**

| Param   | Type   | Default  | Description          |
| ------- | ------ | -------- | -------------------- |
| `q`     | string | required | Query                |
| `limit` | int    | 5        | Results per category |

**Example:**

```
/mix?q=elon+musk&limit=3
```

**Response:**

```json
{
  "query": "elon musk",
  "results": {
    "web": [...],
    "news": [...],
    "images": [...],
    "videos": [...]
  }
}
```

---

## ⚖️ Rate Limiting

* Default: **60 requests/minute per IP**
* If exceeded → `429 Too Many Requests`

---

## 🔐 Authentication

(Currently none, public free API. You can add API keys if needed.)

---

## ⏱️ Performance

* Cached results (60s) to speed up repeat queries
* Gzip compression enabled
* Responses <200ms for warm queries

