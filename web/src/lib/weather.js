export const WMO_CODES = {
  0:  { label: 'Clear',                  icon: 'clear' },
  1:  { label: 'Mostly Clear',           icon: 'mostly-clear' },
  2:  { label: 'Partly Cloudy',          icon: 'partly-cloudy' },
  3:  { label: 'Overcast',               icon: 'overcast' },
  45: { label: 'Fog',                    icon: 'fog' },
  48: { label: 'Icy Fog',                icon: 'rime-fog' },
  51: { label: 'Light Drizzle',          icon: 'light-drizzle' },
  53: { label: 'Drizzle',                icon: 'moderate-drizzle' },
  55: { label: 'Heavy Drizzle',          icon: 'dense-drizzle' },
  56: { label: 'Light Freezing Drizzle', icon: 'light-freezing-drizzle' },
  57: { label: 'Freezing Drizzle',       icon: 'dense-freezing-drizzle' },
  61: { label: 'Light Rain',             icon: 'light-rain' },
  63: { label: 'Rain',                   icon: 'moderate-rain' },
  65: { label: 'Heavy Rain',             icon: 'heavy-rain' },
  66: { label: 'Light Freezing Rain',    icon: 'light-freezing-rain' },
  67: { label: 'Freezing Rain',          icon: 'heavy-freezing-rain' },
  71: { label: 'Light Snow',             icon: 'slight-snowfall' },
  73: { label: 'Snow',                   icon: 'moderate-snowfall' },
  75: { label: 'Heavy Snow',             icon: 'heavy-snowfall' },
  77: { label: 'Snow Grains',            icon: 'snowflake' },
  80: { label: 'Light Showers',          icon: 'light-rain' },
  81: { label: 'Showers',               icon: 'moderate-rain' },
  82: { label: 'Heavy Showers',          icon: 'heavy-rain' },
  85: { label: 'Light Snow Showers',     icon: 'slight-snowfall' },
  86: { label: 'Snow Showers',           icon: 'heavy-snowfall' },
  95: { label: 'Thunderstorm',           icon: 'thunderstorm' },
  96: { label: 'T-storm w/ Hail',        icon: 'thunderstorm-with-hail' },
  99: { label: 'T-storm w/ Hail',        icon: 'thunderstorm-with-hail' },
};

async function fetchWeatherOpenMeteo(lat, lon) {
  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=3&temperature_unit=fahrenheit`;
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();

    const currentCode = data.current?.weather_code;
    const isDay = data.current?.is_day !== 0;
    const currentWmo = WMO_CODES[currentCode] ?? { label: 'Unknown', icon: 'clear' };
    const currentIcon = !isDay && (currentCode === 0 || currentCode === 1) ? 'clear-night' : currentWmo.icon;

    const forecast = [1, 2].map((i) => {
      const code = data.daily?.weather_code?.[i];
      const wmo = WMO_CODES[code] ?? { label: 'Unknown', icon: 'clear' };
      const dateStr = data.daily?.time?.[i];
      const day = dateStr
        ? new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' })
        : '';
      return {
        day,
        high: Math.round(data.daily?.temperature_2m_max?.[i] ?? 0),
        low: Math.round(data.daily?.temperature_2m_min?.[i] ?? 0),
        label: wmo.label,
        icon: wmo.icon,
      };
    });

    return {
      current: {
        temp: Math.round(data.current?.temperature_2m ?? 0),
        label: currentWmo.label,
        icon: currentIcon,
      },
      forecast,
    };
  } catch {
    return null;
  }
}

async function fetchWeatherNWS(lat, lon) {
  try {
    const pointsRes = await fetch(
      `https://api.weather.gov/points/${lat},${lon}`,
      { headers: { 'User-Agent': 'postmarked-app/1.0 (contact@werehere.app)' } },
    );
    if (!pointsRes.ok) return null;
    const pointsData = await pointsRes.json();

    const forecastUrl = pointsData.properties?.forecast;
    const forecastHourlyUrl = pointsData.properties?.forecastHourly;
    if (!forecastUrl || !forecastHourlyUrl) return null;

    const ua = { headers: { 'User-Agent': 'postmarked-app/1.0 (contact@werehere.app)' } };
    const [dailyRes, hourlyRes] = await Promise.all([
      fetch(forecastUrl, ua),
      fetch(forecastHourlyUrl, ua),
    ]);
    if (!dailyRes.ok || !hourlyRes.ok) return null;

    const [dailyData, hourlyData] = await Promise.all([dailyRes.json(), hourlyRes.json()]);

    const hourlyPeriods = hourlyData.properties?.periods ?? [];
    const dailyPeriods = dailyData.properties?.periods ?? [];

    const currentPeriod = hourlyPeriods[0];
    if (!currentPeriod) return null;

    const daytimePeriods = dailyPeriods.filter((p) => p.isDaytime).slice(1, 3);
    const forecast = daytimePeriods.map((p) => {
      const night = dailyPeriods.find((n) => !n.isDaytime && n.number === p.number + 1);
      return {
        day: new Date(p.startTime).toLocaleDateString('en-US', { weekday: 'short' }),
        high: p.temperature,
        low: night?.temperature ?? p.temperature - 15,
        label: p.shortForecast,
        icon: 'clear',
      };
    });

    return {
      current: {
        temp: currentPeriod.temperature,
        label: currentPeriod.shortForecast,
        icon: 'clear',
      },
      forecast,
    };
  } catch {
    return null;
  }
}

export async function fetchWeather(lat, lon) {
  return (await fetchWeatherOpenMeteo(lat, lon)) ?? (await fetchWeatherNWS(lat, lon));
}
