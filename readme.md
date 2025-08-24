# LLM Web Search API

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](/LICENSE)

A high-performance, feature-rich API designed to give Large Language Models (LLMs) and other applications access to live web data. It provides endpoints for Google searching, extracting clean content from any URL, and fetching YouTube video subtitles.

Built with FastAPI, it is fast, asynchronous, and easy to deploy on platforms like Render.

---

## 核心功能 (Core Features)

-   **🔍 Google Search:** A simple endpoint to get a clean list of Google search results for any query.
-   **📄 Content Extraction:** Scrapes a given URL and uses the powerful `trafilatura` library to extract only the main, readable content, removing ads, navbars, and other boilerplate.
-   **📺 YouTube Subtitles:** Fetches full subtitles for any YouTube video, intelligently falling back from manual transcripts to auto-generated captions.
-   **⚡ Fast & Async:** Built on FastAPI and `httpx` for high-concurrency and non-blocking I/O.
-   **🛡️ Rate Limiting:** Comes with a built-in rate limiter to protect your service from abuse.
-   **☁️ Deployment Ready:** Designed for easy, hassle-free deployment on cloud services like Render.

---

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
