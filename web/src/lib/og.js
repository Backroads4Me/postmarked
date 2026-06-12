export function plainText(value) {
  return String(value || '')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function mediaOgImage(media) {
  const item = (media || []).find((m) => m?.kind === 'photo') || (media || [])[0];
  if (!item) return undefined;
  if (item.kind === 'video') {
    return item.derivative_paths?.poster || `/media/${item.id}/poster`;
  }
  return item.derivative_paths?.webp || item.derivative_paths?.avif || `/media/${item.id}/webp`;
}
