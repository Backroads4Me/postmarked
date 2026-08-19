import assert from 'node:assert/strict';
import test from 'node:test';

import { selectLiveStop } from './stopLive.js';


const TODAY = '2026-08-19';

function stop(id, start, end, options = {}) {
  return {
    id,
    start_date: start,
    end_date: end,
    sort_order: options.sortOrder ?? 0,
    is_current: options.isCurrent ?? false,
  };
}

test('selects the only active stop', () => {
  const active = stop('active', '2026-08-18', '2026-08-20');
  assert.equal(selectLiveStop([active], TODAY), active);
});

test('selects the latest overlapping stop by deterministic route order', () => {
  const earlier = stop('earlier', '2026-08-15', '2026-08-21', { sortOrder: 1 });
  const later = stop('later', '2026-08-18', '2026-08-22', { sortOrder: 2 });
  assert.equal(selectLiveStop([later, earlier], TODAY), later);
});

test('prefers the explicitly current stop in an overlap', () => {
  const explicit = stop('explicit', '2026-08-15', '2026-08-21', {
    isCurrent: true,
    sortOrder: 1,
  });
  const later = stop('later', '2026-08-18', '2026-08-22', { sortOrder: 2 });
  assert.equal(selectLiveStop([later, explicit], TODAY), explicit);
});

test('returns no stop for an empty itinerary', () => {
  assert.equal(selectLiveStop([], TODAY), null);
});

test('returns no stop when every stop is in the past', () => {
  const past = stop('past', '2026-08-10', '2026-08-12');
  assert.equal(selectLiveStop([past], TODAY), null);
});

test('returns no stop when every stop is in the future', () => {
  const future = stop('future', '2026-08-22', '2026-08-25');
  assert.equal(selectLiveStop([future], TODAY), null);
});
