# TODO

## Remove unused weather icon assets

Weather icons are no longer rendered in the UI. The `icon` field is still
populated by `fetchWeather` / `fetchWeatherNWS` but nothing displays it.

**Files to delete:**
- `web/public/weather-icons/` — 23 PNG files

**Code to clean up in `web/src/lib/weather.js`:**
- `WMO_CODES` map — the `icon` field on each entry (or the whole map if
  `label` is also no longer needed elsewhere)
- The `icon` / `currentIcon` logic in `fetchWeatherOpenMeteo`
- The hard-coded `icon: 'clear'` fallbacks in `fetchWeatherNWS`
- The `icon` field on the returned `current` and `forecast` objects

**Verify before removing:**
- Confirm no template references `weather.current.icon` or
  `weather.forecast[*].icon`
- Check `web/src/pages/design-lab/postmarked-components.astro` for any
  weather icon usage
- Delete `web/dist/client/weather-icons/` if the dist directory is
  committed (it shouldn't be)
