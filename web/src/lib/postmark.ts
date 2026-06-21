export interface PostmarkOptions {
  city?: string | null;
  state?: string | null;
  date?: string | null;
  year?: string | null;
  color?: string | null;
  size?: number | string | null;
  rotate?: number | string | null;
  landmark?: string | null;
  className?: string | null;
}

function escapeXml(value: unknown) {
  return String(value ?? '').replace(/[<>&'"]/g, (char) => {
    const entities: Record<string, string> = {
      '<': '&lt;',
      '>': '&gt;',
      '&': '&amp;',
      "'": '&apos;',
      '"': '&quot;',
    };
    return entities[char] || char;
  });
}

function numeric(value: number | string | null | undefined, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function postmarkSvg(options: PostmarkOptions = {}) {
  const city = String(options.city || 'MOAB').toUpperCase();
  const state = String(options.state || 'UT').toUpperCase();
  const date = String(options.date || 'OCT 26').toUpperCase();
  const year = String(options.year || '25').toUpperCase();
  const landmark = String(options.landmark || '').toUpperCase();
  const color = String(options.color || 'var(--ember)');
  const size = numeric(options.size, 220);
  const rotate = numeric(options.rotate, -6);
  const className = options.className ? ` ${escapeXml(options.className)}` : '';

  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 2;
  const rInner = r - 6;

  const maxCityWidth = rInner * 2 * 0.86;
  const naturalCitySize = size * 0.22;
  const naturalCityWidth = city.length * naturalCitySize * 0.62;
  const citySize = naturalCityWidth > maxCityWidth
    ? +(naturalCitySize * (maxCityWidth / naturalCityWidth)).toFixed(2)
    : +naturalCitySize.toFixed(2);

  const topSize = +(size * 0.125).toFixed(2);
  const dateSize = +(size * 0.078).toFixed(2);
  const topLetterSpacing = +(size * 0.014).toFixed(2);
  const dateLetterSpacing = +(size * 0.005).toFixed(2);

  const dateTokens = date.split(/\s+/).filter(Boolean);
  const dateTspans = [
    ...dateTokens.map((token, index) => {
      const suffix = year && index === dateTokens.length - 1 ? ',' : '';
      return index === 0
        ? `<tspan>${escapeXml(token + suffix)}</tspan>`
        : `<tspan dx="0.32em">${escapeXml(token + suffix)}</tspan>`;
    }),
    year ? `<tspan dx="0.32em">${escapeXml(year)}</tspan>` : '',
  ].join('');

  const barCount = 6;
  const totalHeight = r * 1.125;
  const gap = totalHeight / (barCount - 1);
  const amplitude = Math.max(2.5, size * 0.022);
  const halfWave = (size * 0.3) / 2;
  const strokeWidth = Math.max(2, Math.round(size * 0.018));
  const yTop = cy - totalHeight / 2;
  const xEnd = cx + r + size * 0.62;
  const xGap = size * 0.03;

  let bars = '';
  for (let index = 0; index < barCount; index += 1) {
    const y = yTop + index * gap;
    const dy = y - cy;
    const xArc = cx + Math.sqrt(Math.max(0, r * r - dy * dy));
    const xStart = xArc + xGap;
    if (xStart >= xEnd - halfWave) continue;

    let d = `M ${xStart.toFixed(2)} ${y.toFixed(2)}`;
    let x = xStart;
    let direction = 1;

    while (x + halfWave <= xEnd + 0.01) {
      const midX = x + halfWave / 2;
      const midY = y + direction * amplitude;
      const nextX = x + halfWave;
      d += ` Q ${midX.toFixed(2)} ${midY.toFixed(2)}, ${nextX.toFixed(2)} ${y.toFixed(2)}`;
      x = nextX;
      direction *= -1;
    }

    if (x < xEnd - 0.5) d += ` L ${xEnd.toFixed(2)} ${y.toFixed(2)}`;
    bars += `<path d="${d}" stroke="${escapeXml(color)}" stroke-width="${strokeWidth}" fill="none" stroke-linecap="round"/>`;
  }

  const contentWidth = xEnd + 4;
  const pad = Math.round(size * 0.18);
  const outerWidth = contentWidth + pad * 2;
  const outerHeight = size + pad * 2;
  const aria = `${city} ${state} postmark, ${date} ${year}`.trim();

  return `<svg class="postmark-svg${className}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${outerWidth} ${outerHeight}" width="${outerWidth}" height="${outerHeight}" role="img" aria-label="${escapeXml(aria)}">
    <g transform="translate(${pad} ${pad}) rotate(${rotate} ${contentWidth / 2} ${size / 2})">
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${escapeXml(color)}" stroke-width="2.2" opacity="0.92"/>
      <circle cx="${cx}" cy="${cy}" r="${rInner}" fill="none" stroke="${escapeXml(color)}" stroke-width="1" stroke-dasharray="3 3" opacity="0.55"/>
      <text x="${cx}" y="${cy - size * 0.19}" text-anchor="middle" class="postmark-svg__top" font-size="${topSize}" letter-spacing="${topLetterSpacing}" fill="${escapeXml(color)}" opacity="0.95">★ ${escapeXml(landmark || state)} ★</text>
      <text x="${cx}" y="${cy - size * 0.025}" text-anchor="middle" dominant-baseline="central" class="postmark-svg__city" font-size="${citySize}" fill="${escapeXml(color)}">${escapeXml(city)}</text>
      <line x1="${cx - r * 0.42}" y1="${cy + size * 0.14}" x2="${cx + r * 0.42}" y2="${cy + size * 0.14}" stroke="${escapeXml(color)}" stroke-width="1.2" opacity="0.55"/>
      <text x="${cx}" y="${cy + size * 0.28}" text-anchor="middle" class="postmark-svg__date" font-size="${dateSize}" letter-spacing="${dateLetterSpacing}" fill="${escapeXml(color)}" opacity="0.95">${dateTspans}</text>
      <g opacity="0.92">${bars}</g>
    </g>
  </svg>`;
}
