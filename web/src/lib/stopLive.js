const DATE_PREFIX_RE = /^(\d{4}-\d{2}-\d{2})/;

function parseStopDate(value) {
  if (!value) return null;
  const match = typeof value === 'string' && value.match(DATE_PREFIX_RE);
  if (match) return match[1];
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}

function todayUtcDate() {
  return new Date().toISOString().slice(0, 10);
}

/** Mirrors journey._contains_today using UTC calendar dates. */
export function stopContainsToday(stop, today = todayUtcDate()) {
  const start = parseStopDate(stop?.start_date);
  if (!start) return false;
  const end = parseStopDate(stop?.end_date);
  if (!end) return start <= today;
  return start <= today && today <= end;
}

/** Mirrors journey._is_live_current_stop using UTC calendar dates. */
export function stopIsLive(stop, today = todayUtcDate()) {
  if (stopContainsToday(stop, today)) return true;
  if (!stop?.is_current) return false;

  const start = parseStopDate(stop?.start_date);
  if (start && start > today) return false;

  const end = parseStopDate(stop?.end_date);
  return !end || end >= today;
}
