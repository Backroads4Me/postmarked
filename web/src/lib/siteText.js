import { apiUrl } from './api.js';

export async function loadSiteText() {
  try {
    const res = await fetch(apiUrl('/api/site-text'));
    if (!res.ok) return {};
    const rows = await res.json();
    return Object.fromEntries(
      rows.map((row) => [`${row.page_key}.${row.section_key}`, row])
    );
  } catch (error) {
    console.error('Failed to load site text', error);
    return {};
  }
}

export function sectionText(sections, key, fallback) {
  return sections[key] || fallback;
}
