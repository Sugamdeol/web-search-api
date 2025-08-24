

## API Documentation

For detailed information on each endpoint, request/response formats, and `curl` examples, please see the **[API Documentation (APIDOCS.md)](APIDOCS.md)**.

The API also provides automatic, interactive documentation via Swagger UI. Once deployed, you can access it at `/docs`.
-   **Example:** `https://your-api-url.onrender.com/docs`

---

## 技术栈 (Tech Stack)

-   **Framework:** FastAPI
-   **HTTP Client:** httpx
-   **Web Scraping/Parsing:** Trafilatura, BeautifulSoup4
-   **Search:** googlesearch-python
-   **YouTube:** youtube-transcript-api
-   **Rate Limiting:** slowapi

---

## 部署 (Deployment on Render)

This API is optimized for deployment on Render's free tier.

1.  **Fork this Repository:** Create your own copy of this project on GitHub.
2.  **Create a New Web Service on Render:**
    -   Connect your GitHub account and select your forked repository.
3.  **Configure the Service:**
    -   **Environment:** `Python 3`
    -   **Build Command:** `pip install -r requirements.txt`
    -   **Start Command:** `uvicorn app:app --host 0.0.0.0 --port 10000`
4.  **Deploy:** Click "Create Web Service". Render will handle the rest. Your API will be live at the URL provided.

> **Note on Free Tier:** Render's free services may "spin down" after a period of inactivity. The first request after a spin-down might take a bit longer as the service wakes up.

---

## 本地开发设置 (Setup for Local Development)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/llm-web-search-api.git
    cd llm-web-search-api
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the local server:**
    ```bash
    uvicorn app:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

---

## 许可证 (License)

This project is licensed under the MIT License. See the `LICENSE` file for details.
```

---

### `APIDOCS.md`

Yeh file API ke technical details batati hai. Har endpoint, uske parameters, aur example responses yahan pe hain.

```markdown
# API Documentation

This document provides detailed information about the available endpoints for the LLM Web Search API.

-   **Base URL:** `https://your-api-url.onrender.com`
-   All request and response bodies are in `application/json` format.

---

## 1. Google Search

Performs a Google search and returns a list of URLs and snippets.

-   **Endpoint:** `POST /search`
-   **Method:** `POST`

### Request Body

| Parameter        | Type    | Required | Description                                                  |
| ---------------- | ------- | -------- | ------------------------------------------------------------ |
| `q`              | string  | Yes      | The search query you want to perform.                        |
| `num`            | integer | No       | The number of results to return. Default is `10`. Max is `20`. |
| `fetch_snippets` | boolean | No       | If `true`, also fetches the title and meta description for each URL. Default is `true`. |

### Success Response (200 OK)

```json
{
  "query": "best free python courses",
  "count": 2,
  "results": [
    {
      "url": "https://www.coursera.org/specializations/python-3-programming",
      "title": "Python 3 Programming Specialization - Coursera",
      "description": "Launch your career in programming. Build job-ready skills for an in-demand career and earn a credential from University of Michigan."
    },
    {
      "url": "https://www.codecademy.com/learn/learn-python-3",
      "title": "Learn Python 3 | Codecademy",
      "description": "Learn the basics of Python 3, one of the most popular and versatile programming languages. No prior programming experience required."
    }
  ]
}
```

### Error Response (503 Service Unavailable)

This occurs if the server is temporarily blocked by Google.

```json
{
  "detail": "Failed to fetch search results. Server might be blocked. Error: <error_details>"
}
```

### Example `curl` Request

```bash
curl -X POST "https://your-api-url.onrender.com/search" \
-H "Content-Type: application/json" \
-d '{
  "q": "latest AI research papers",
  "num": 5
}'
```

---

## 2. Extract Web Content

Extracts the main article text from a given URL.

-   **Endpoint:** `POST /extract`
-   **Method:** `POST`

### Request Body

| Parameter | Type   | Required | Description                |
| --------- | ------ | -------- | -------------------------- |
| `url`     | string | Yes      | The URL to scrape content from. |

### Success Response (200 OK)

```json
{
  "text": "This is the main content of the article, with all the ads and boilerplate removed. It provides a clean, readable text block perfect for feeding into a language model...",
  "title": "Title of the Article",
  "url": "https://example.com/some-article"
}
```

### Example `curl` Request

```bash
curl -X POST "https://your-api-url.onrender.com/extract" \
-H "Content-Type: application/json" \
-d '{
  "url": "https://www.freecodecamp.org/news/what-is-api-in-plain-english/"
}'
```

---

## 3. Get YouTube Subtitles

Fetches the full subtitles for a YouTube video. It prioritizes manual transcripts and falls back to auto-generated captions if necessary.

-   **Endpoint:** `POST /yt/subtitles`
-   **Method:** `POST`

### Request Body

| Parameter   | Type           | Required | Description                                                  |
| ----------- | -------------- | -------- | ------------------------------------------------------------ |
| `video_id`  | string         | Yes      | The YouTube video ID or full URL.                            |
| `languages` | array[string]  | No       | A list of language codes to try, in order of preference. Default is `["en", "en-US"]`. |

### Success Response (200 OK)

```json
{
  "video_id": "ji5_MqicxSo",
  "language_code": "en",
  "is_generated": true,
  "text": "When I was in high school I was your classic nerd. And I also was a computer science nerd... (full text of subtitles here)",
  "segments": [
    {
      "text": "When I was in high school I was your classic nerd.",
      "start": 10.5,
      "duration": 4.2
    },
    {
      "text": "And I also was a computer science nerd.",
      "start": 14.7,
      "duration": 3.0
    }
  ]
}
```

### Error Response (404 Not Found)

This occurs if no subtitles (manual or auto-generated) are found for the video.

```json
{
  "detail": "Could not find subtitles. Reason: No manual or auto-generated subtitles found for the given languages."
}
```

### Example `curl` Request

```bash
curl -X POST "https://your-api-url.onrender.com/yt/subtitles" \
-H "Content-Type: application/json" \
-d '{
  "video_id": "https://www.youtube.com/watch?v=ji5_MqicxSo"
}'
```
