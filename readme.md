# TurboDuck Search API

A fast, free search API on Render using duckduckgo-search.
Endpoints: `/search`, `/news`, `/images`, `/videos`, `/suggest`, `/mix`.

## Deploy
1. Push these files to a GitHub repo.
2. Create a new Web Service on Render from the repo.
3. Render will use `render.yaml` and deploy.

## Usage examples
- Web search  
  `/search?q=ai tools&limit=10&page=1&region=in-en&safesearch=moderate&site=example.com`

- News  
  `/news?q=india&freshness=7d`

- Images  
  `/images?q=virat kohli&size=Large&color=mono`

- Videos  
  `/videos?q=funny memes`

- Suggestions  
  `/suggest?q=indi`

- Mixed (web + news + images)  
  `/mix?q=iphone 16`

## Notes
- Built-in gzip, CORS, caching, rate limit.
- Pagination available by `page` and `limit`.
- For production, replace in-memory cache with Redis and tighten rate limits.
