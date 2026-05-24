/**
 * Extracts "City, ST" from a full address string like
 * "Manzanita Campground, 6655 N Hwy 89A, Sedona, AZ 86336, USA"
 */
export function cityStateFromAddress(address?: string | null): string {
  if (!address) return '';
  const parts = address.split(',').map((p) => p.trim()).filter(Boolean);
  if (parts.length < 3) return '';
  const stateRe = /^([A-Z]{2})(?:\s+\d{5}(?:-\d{4})?)?$/;
  for (let i = parts.length - 1; i > 0; i--) {
    const match = parts[i].match(stateRe);
    if (match && parts[i - 1]) return `${parts[i - 1]}, ${match[1]}`;
  }
  return '';
}
