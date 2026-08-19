import { stopIsLive } from './stopLive.js';


const HOME_STOP_STATES = new Set(['live', 'previous', 'upcoming']);

function todayUtcDate() {
  return new Date().toISOString().slice(0, 10);
}

function stopStartDate(stop) {
  const match = typeof stop?.start_date === 'string'
    ? stop.start_date.match(/^(\d{4}-\d{2}-\d{2})/)
    : null;
  return match?.[1] || null;
}

export function resolveHomeStopState(homeData, today = todayUtcDate()) {
  const stop = homeData?.current_stop;
  if (!stop) return null;
  if (HOME_STOP_STATES.has(homeData?.current_stop_kind)) {
    return homeData.current_stop_kind;
  }
  if (homeData?.current_stop_is_live === true || stopIsLive(stop, today)) {
    return 'live';
  }
  const start = stopStartDate(stop);
  return start && start > today ? 'upcoming' : 'previous';
}

export function homeStopLabel(state, liveLabel = 'Currently At') {
  return homeStopPresentation(state, liveLabel)?.label ?? null;
}

export function homeStopPresentation(state, liveLabel = 'Currently At') {
  if (state === 'live') {
    return {
      label: liveLabel,
      landmark: null,
      arrivalLabel: 'Arrived',
      isLive: true,
      showWeather: true,
      useDepartureDate: false,
    };
  }
  if (state === 'previous') {
    return {
      label: 'Last Stop',
      landmark: 'Last Stop',
      arrivalLabel: 'Arrived',
      isLive: false,
      showWeather: false,
      useDepartureDate: true,
    };
  }
  if (state === 'upcoming') {
    return {
      label: 'Next Stop',
      landmark: 'Next Stop',
      arrivalLabel: 'Arriving',
      isLive: false,
      showWeather: false,
      useDepartureDate: false,
    };
  }
  return null;
}
