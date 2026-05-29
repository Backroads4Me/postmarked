export const MAP_COLORS = {
  campground: "#6FA694",
  trailhead: "#7AB8D6",
  fuel: "#EC8068",
  restaurant: "#c46f9f",
  attraction: "#9f6fc4",
  other: "#888888",
  photo: "#e8c44a",
  current: "#e05252",
  active: "#BD3325",
  route: "#BD3325",
  background: "#101419",
  markerGlyph: "#101419",
  markerBorder: "#ffffff",
};

export function mapPoiColor(type) {
  return MAP_COLORS[type] ?? MAP_COLORS.other;
}
