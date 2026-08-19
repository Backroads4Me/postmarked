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

function compareStopOrder(left, right) {
  const leftStart = parseStopDate(left?.start_date) || '';
  const rightStart = parseStopDate(right?.start_date) || '';
  if (leftStart !== rightStart) return leftStart.localeCompare(rightStart);

  const leftOrder = Number.isInteger(left?.sort_order) ? left.sort_order : -1;
  const rightOrder = Number.isInteger(right?.sort_order) ? right.sort_order : -1;
  if (leftOrder !== rightOrder) return leftOrder - rightOrder;

  return String(left?.id || left?.slug || '').localeCompare(
    String(right?.id || right?.slug || ''),
  );
}

/** Select one live stop, preferring an explicit marker before route order. */
export function selectLiveStop(stops, today = todayUtcDate()) {
  const live = (stops || []).filter(stop => stopIsLive(stop, today));
  const explicit = live.filter(stop => stop?.is_current);
  const candidates = explicit.length > 0 ? explicit : live;
  return candidates.reduce(
    (selected, stop) => !selected || compareStopOrder(stop, selected) > 0 ? stop : selected,
    null,
  );
}
