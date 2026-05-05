# Goodpath Web

Astro frontend for Goodpath. The app is server-rendered with React islands for interactive pieces such as maps, comments, quick posting, imports, and admin controls.

## Stack

- Astro 6
- React 19 islands
- Tailwind 4
- MapLibre GL JS
- PMTiles vector tiles through Caddy

## Development

From the repo root, Docker is the preferred path:

```bash
docker compose -f compose/docker-compose.yml -f compose/docker-compose.dev.yml up --build
```

The web dev server is available at:

- Direct Astro dev server: http://localhost:4321
- Caddy dev proxy: http://localhost:8080

For direct frontend work:

```bash
cd web
npm install
API_BASE_URL=http://localhost:8000 npm run dev
```

## API Calls

Use `src/lib/api.js`:

- `apiUrl(path)` for Astro server-side fetches. In Docker it resolves to `http://api:8000`.
- `clientApiUrl(path)` for browser-side fetches. It always returns root-relative `/api/...` paths that work through Caddy.

Browser code should never call `http://api:8000` directly.

## Useful Commands

```bash
npm run dev
npm run build
npm run preview
```

`npm run build` is the main frontend verification command used before local testing.
