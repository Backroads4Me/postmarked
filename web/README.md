# Postmarked Web

Astro frontend for Postmarked. The app is server-rendered with React islands for interactive pieces such as maps, comments, quick posting, imports, and admin controls.

## Stack

- Astro 6
- React 19 islands
- Tailwind 4
- Google Maps by default
- Optional MapLibre GL JS + PMTiles vector tiles

## Development

From the repo root, Docker is the preferred path:

```bash
docker compose up --build
```

The web dev server is available at:

- Astro dev server: http://localhost:4321

For direct frontend work:

```bash
cd web
npm install
API_BASE_URL=http://localhost:8000 npm run dev
```

## API Calls

Use `src/lib/api.js`:

- `apiUrl(path)` for Astro server-side fetches. In Docker it resolves to `http://api:8000`.
- `clientApiUrl(path)` for browser-side fetches. It always returns root-relative `/api/...` paths that work through the Astro middleware proxy.

Browser code should never call `http://api:8000` directly.

## Maps

The default map provider is Google Maps:

```env
PUBLIC_MAP_PROVIDER=google
PUBLIC_GOOGLE_MAPS_API_KEY=<your browser API key>
```

Set `PUBLIC_MAP_PROVIDER=maplibre` to use the optional PMTiles-backed MapLibre path instead.

## Useful Commands

```bash
npm run dev
npm run build
npm run preview
```

`npm run build` is the main frontend verification command used before local testing.
