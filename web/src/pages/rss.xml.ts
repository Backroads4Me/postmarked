import { apiUrl } from '../lib/api.js';

export const prerender = false;

function xmlEscape(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function itemLink(origin: string, item: any): string {
  if (item.trip_slug) {
    const base = new URL(`/trips/${item.trip_slug}`, origin);
    if (item.kind === 'stop' && item.stop_slug) base.hash = `stop-${item.stop_slug}`;
    if (item.kind === 'post' && item.id) base.hash = `post-${item.id}`;
    return base.toString();
  }
  return new URL('/timeline', origin).toString();
}

export async function GET({ url }: { url: URL }) {
  const res = await fetch(apiUrl('/api/timeline?limit=50&offset=0'));
  const data = res.ok ? await res.json() : { updates: [] };
  const origin = url.origin;
  const items = (data.updates ?? []).map((item: any) => {
    const link = itemLink(origin, item);
    const description = item.body || item.summary || item.place_name || item.address_label || '';
    const pubDate = item.posted_at ? new Date(item.posted_at).toUTCString() : new Date().toUTCString();
    return `
      <item>
        <title>${xmlEscape(item.title)}</title>
        <link>${xmlEscape(link)}</link>
        <guid isPermaLink="true">${xmlEscape(link)}</guid>
        <pubDate>${xmlEscape(pubDate)}</pubDate>
        <description>${xmlEscape(description)}</description>
      </item>`;
  }).join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Postmarked updates</title>
    <link>${xmlEscape(origin)}</link>
    <description>Latest public travel updates from Postmarked.</description>
    <language>en-us</language>
    ${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=300',
    },
  });
}
