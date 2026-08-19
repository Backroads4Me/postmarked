import assert from 'node:assert/strict';
import test from 'node:test';

import {
  homeStopLabel,
  homeStopPresentation,
  resolveHomeStopState,
} from './homeStopState.js';


const TODAY = '2026-08-19';

test('presents an active itinerary as live', () => {
  const home = {
    current_stop: { start_date: '2026-08-18', end_date: '2026-08-20' },
    current_stop_kind: 'live',
  };

  assert.equal(resolveHomeStopState(home, TODAY), 'live');
  assert.equal(homeStopLabel('live', 'Currently At'), 'Currently At');
});

test('presents an ended itinerary as the previous stop', () => {
  const home = {
    current_stop: { start_date: '2026-08-14', end_date: '2026-08-17' },
    current_stop_kind: 'previous',
  };

  assert.equal(resolveHomeStopState(home, TODAY), 'previous');
  assert.equal(homeStopLabel('previous'), 'Last Stop');
});

test('returns no state for an empty itinerary', () => {
  assert.equal(resolveHomeStopState({ current_stop: null }, TODAY), null);
  assert.equal(homeStopLabel(null), null);
});

test('presents an all-future itinerary as upcoming', () => {
  const home = {
    current_stop: { start_date: '2026-08-22', end_date: '2026-08-24' },
    current_stop_kind: 'upcoming',
  };

  const state = resolveHomeStopState(home, TODAY);
  const presentation = homeStopPresentation(state);
  assert.equal(state, 'upcoming');
  assert.equal(presentation.label, 'Next Stop');
  assert.equal(presentation.landmark, 'Next Stop');
  assert.equal(presentation.arrivalLabel, 'Arriving');
  assert.equal(presentation.showWeather, false);
  assert.notEqual(presentation.label, 'Last Stop');
});
