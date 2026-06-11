const SITE_TZ = import.meta.env.PUBLIC_ADMIN_TIMEZONE || 'America/New_York';
const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/;

function isDateOnly(value) {
  return typeof value === 'string' && DATE_ONLY_RE.test(value);
}

function dateOnlyAsUtcNoon(value) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day, 12));
}

function dateForDisplay(value) {
  return isDateOnly(value) ? dateOnlyAsUtcNoon(value) : new Date(value);
}

function displayTimeZone(value) {
  return isDateOnly(value) ? 'UTC' : SITE_TZ;
}

function dateParts(value) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: displayTimeZone(value),
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  })
    .formatToParts(dateForDisplay(value))
    .filter((part) => part.type !== 'literal')
    .reduce((acc, part) => ({ ...acc, [part.type]: Number(part.value) }), {});
}

export function formatDate(dateStr, options = {}) {
  if (!dateStr) return '';
  try {
    return dateForDisplay(dateStr).toLocaleDateString('en-US', {
      timeZone: displayTimeZone(dateStr),
      ...options,
    });
  } catch {
    return '';
  }
}

export function formatDateRange(start, end) {
  if (!start) return '';

  const defaultOptions = { month: 'short', day: 'numeric', year: 'numeric' };
  if (!end) return formatDate(start, defaultOptions);

  try {
    const startParts = dateParts(start);
    const endParts = dateParts(end);

    if (startParts.year === endParts.year && startParts.month === endParts.month) {
      const startLabel = formatDate(start, { month: 'short', day: 'numeric' });
      return `${startLabel}-${endParts.day}, ${endParts.year}`;
    }

    return `${formatDate(start, defaultOptions)} - ${formatDate(end, defaultOptions)}`;
  } catch {
    return formatDate(start, defaultOptions);
  }
}

export function toDateInput(iso) {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: displayTimeZone(iso),
    }).format(dateForDisplay(iso));
  } catch {
    return '';
  }
}
