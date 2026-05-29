export const WMO_CODES = {
  0:  { label: 'Clear' },
  1:  { label: 'Mostly Clear' },
  2:  { label: 'Partly Cloudy' },
  3:  { label: 'Overcast' },
  45: { label: 'Fog' },
  48: { label: 'Icy Fog' },
  51: { label: 'Light Drizzle' },
  53: { label: 'Drizzle' },
  55: { label: 'Heavy Drizzle' },
  56: { label: 'Light Freezing Drizzle' },
  57: { label: 'Freezing Drizzle' },
  61: { label: 'Light Rain' },
  63: { label: 'Rain' },
  65: { label: 'Heavy Rain' },
  66: { label: 'Light Freezing Rain' },
  67: { label: 'Freezing Rain' },
  71: { label: 'Light Snow' },
  73: { label: 'Snow' },
  75: { label: 'Heavy Snow' },
  77: { label: 'Snow Grains' },
  80: { label: 'Light Showers' },
  81: { label: 'Showers' },
  82: { label: 'Heavy Showers' },
  85: { label: 'Light Snow Showers' },
  86: { label: 'Snow Showers' },
  95: { label: 'Thunderstorm' },
  96: { label: 'T-storm w/ Hail' },
  99: { label: 'T-storm w/ Hail' },
};

async function fetchWeatherOpenMeteo(lat, lon) {
  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=3&temperature_unit=fahrenheit`;
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();

    const currentCode = data.current?.weather_code;
    const currentWmo = WMO_CODES[currentCode] ?? { label: 'Unknown' };

    const forecast = [1, 2].map((i) => {
      const code = data.daily?.weather_code?.[i];
      const wmo = WMO_CODES[code] ?? { label: 'Unknown' };
      const dateStr = data.daily?.time?.[i];
      const day = dateStr
        ? new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' })
        : '';
      return {
        day,
        high: Math.round(data.daily?.temperature_2m_max?.[i] ?? 0),
        low: Math.round(data.daily?.temperature_2m_min?.[i] ?? 0),
        label: wmo.label,
      };
    });

    return {
      current: {
        temp: Math.round(data.current?.temperature_2m ?? 0),
        label: currentWmo.label,
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
      { headers: { 'User-Agent': `postmarked-app/1.0 (${import.meta.env.ADMIN_EMAIL ?? 'contact@example.com'})` } },
    );
    if (!pointsRes.ok) return null;
    const pointsData = await pointsRes.json();

    const forecastUrl = pointsData.properties?.forecast;
    const forecastHourlyUrl = pointsData.properties?.forecastHourly;
    if (!forecastUrl || !forecastHourlyUrl) return null;

    const ua = { headers: { 'User-Agent': `postmarked-app/1.0 (${import.meta.env.ADMIN_EMAIL ?? 'contact@example.com'})` } };
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
      };
    });

    return {
      current: {
        temp: currentPeriod.temperature,
        label: currentPeriod.shortForecast,
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
