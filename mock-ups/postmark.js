/* ─────────────────────────────────────────────────────────────────
   postmark.js  ·  cancellation-stamp postmark, framework-free.

   USAGE (vanilla HTML / Astro / React-rendered HTML / anywhere):

     <div id="stamp"></div>
     <script src="/postmark.js"></script>
     <script>
       Postmark.render(document.getElementById("stamp"), {
         city: "MOAB", state: "UT", date: "OCT 26", year: "25"
       });
     </script>

   Or just get the SVG string and inject it yourself:

     el.innerHTML = Postmark.svg({ city: "MOAB", state: "UT", ... });

   Or build the <img>-friendly data URL:

     img.src = Postmark.dataUrl({ city, state, date, year });

   Required webfonts (load once in your <head>):
     <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
     <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0&family=JetBrains+Mono:wght@700&display=swap" rel="stylesheet">

   Options (all optional):
     city    string   – e.g. "MOAB"           (uppercased automatically)
     state   string   – e.g. "UT"
     date    string   – e.g. "OCT 26"
     year    string   – e.g. "25"
     color   string   – CSS color, default "#BD3325"
     size    number   – px, default 220
     rotate  number   – degrees, default -6
   ───────────────────────────────────────────────────────────────── */

(function (root) {
  "use strict";

  var FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0&family=JetBrains+Mono:wght@700&display=swap');";

  function escapeXml(s) {
    return String(s).replace(/[<>&'"]/g, function (c) {
      return { "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" }[c];
    });
  }

  function svg(opts) {
    opts = opts || {};
    var city   = String(opts.city   != null ? opts.city   : "MOAB"  ).toUpperCase();
    var state  = String(opts.state  != null ? opts.state  : "UT"    ).toUpperCase();
    var date   = String(opts.date   != null ? opts.date   : "OCT 26").toUpperCase();
    var year   = String(opts.year   != null ? opts.year   : "25"    ).toUpperCase();
    var color  = String(opts.color  != null ? opts.color  : "#BD3325");
    var size   = +(opts.size   != null ? opts.size   : 220);
    var rotate = +(opts.rotate != null ? opts.rotate : -6);
    var embedFont = opts.embedFont !== false;

    /* Geometry */
    var cx = size / 2, cy = size / 2;
    var r       = size / 2 - 2;
    var rInner  = r - 6;

    /* Auto-resize city text:
       cap natural width at the inner ring diameter * 0.86 (chord of the
       circle that leaves a small margin from the dotted ring). If the text
       would be wider than that at the default size, shrink the font.
       0.62 is a reasonable average glyph-width for DM Serif Display caps. */
    var maxCityW = rInner * 2 * 0.86;
    var glyphW   = 0.62;
    var fsCityNat = size * 0.22;
    var fsCity = fsCityNat;
    var natural = city.length * fsCityNat * glyphW;
    if (natural > maxCityW) fsCity = fsCityNat * (maxCityW / natural);
    fsCity = +fsCity.toFixed(2);

    var fsTop  = +(size * 0.078).toFixed(2);
    var fsDate = +(size * 0.078).toFixed(2);
    var lsTop  = +(size * 0.014).toFixed(2);
    var lsDate = +(size * 0.005).toFixed(2);

    /* Date row — built from <tspan>s with explicit dx so the spaces don't
       balloon out to monospace cell width. Date can be one or two tokens
       (e.g. "OCT 26"); year can be 2 or 4 digit. */
    var dateTokens = String(date).split(/\s+/).filter(Boolean);
    var dxGap = "0.32em";
    var dateTspans = "";
    for (var di = 0; di < dateTokens.length; di++) {
      dateTspans += (di === 0)
        ? '<tspan>' + escapeXml(dateTokens[di]) + '</tspan>'
        : '<tspan dx="' + dxGap + '">' + escapeXml(dateTokens[di]) + '</tspan>';
    }
    if (year) {
      dateTspans += '<tspan dx="' + dxGap + '">\u00b7</tspan>' +
                    '<tspan dx="' + dxGap + '">' + escapeXml(year) + '</tspan>';
    }

    /* City vertical-centering: middle of the space between the top star
       row and the horizontal divider line, so it stays centered no
       matter how the font size shrinks. */
    var cityY = cy - size * 0.025;

    /* Cancellation bars — 6 wavy lines, left ends on the circle's right
       arc (so the bundle tucks into the circle), right ends all aligned. */
    var barCount = 6;
    var barColor = color;
    var totalH   = r * 1.125;                    // vertical span of bar bundle (lines 25% closer)
    var gap      = totalH / (barCount - 1);
    var amp      = Math.max(2.5, size * 0.022);  // wave amplitude
    var wavelen  = size * 0.30;                  // distance for one full wave
    var halfWave = wavelen / 2;
    var strokeW  = Math.max(2, Math.round(size * 0.018));
    var yTop     = cy - totalH / 2;

    var xEnd     = cx + r + size * 0.62;         // all bars end here
    var xGap     = size * 0.03;                  // small gap from the circle edge

    var bars = "";
    for (var i = 0; i < barCount; i++) {
      var y  = yTop + i * gap;
      var dy = y - cy;
      // Right-side intersection of the circle at this y:
      var xArc = cx + Math.sqrt(Math.max(0, r * r - dy * dy));
      var xStart = xArc + xGap;
      if (xStart >= xEnd - halfWave) continue;   // safety: skip if too short

      var d = "M " + xStart.toFixed(2) + " " + y.toFixed(2);
      // Walk in half-wave segments until we'd overshoot xEnd; finish flush.
      var x = xStart;
      var dir = 1;            // first hump direction (down then up)
      while (x + halfWave <= xEnd + 0.01) {
        var midX = x + halfWave / 2;
        var midY = y + dir * amp;
        var nextX = x + halfWave;
        d += " Q " + midX.toFixed(2) + " " + midY.toFixed(2)
           + ", " + nextX.toFixed(2) + " " + y.toFixed(2);
        x = nextX;
        dir *= -1;
      }
      // Cap with a short straight segment if there's a tiny remainder
      if (x < xEnd - 0.5) d += " L " + xEnd.toFixed(2) + " " + y.toFixed(2);

      bars += '<path d="' + d + '" stroke="' + barColor + '" stroke-width="' +
              strokeW + '" fill="none" stroke-linecap="round"/>';
    }

    /* SVG bounding box — wide enough for the bars + a pad so rotation
       doesn't clip. */
    var W = xEnd + 4;             // content width (origin at circle's left)
    var H = size;
    var pad = Math.round(size * 0.18);
    var outerW = W + pad * 2;
    var outerH = H + pad * 2;

    var fontStyle = embedFont
      ? '<style>' + FONT_IMPORT +
        '.pmTop,.pmDate{font-family:"JetBrains Mono",ui-monospace,monospace;font-weight:700}' +
        '.pmCity{font-family:"DM Serif Display",Georgia,serif}' +
        '</style>'
      : '<style>' +
        '.pmTop,.pmDate{font-family:"JetBrains Mono",ui-monospace,monospace;font-weight:700}' +
        '.pmCity{font-family:"DM Serif Display",Georgia,serif}' +
        '</style>';

    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + outerW + ' ' + outerH + '" ' +
           'width="' + outerW + '" height="' + outerH + '" role="img" aria-label="' +
           escapeXml(city + " " + state + " postmark, " + date + " " + year) + '">' +
           '<defs>' + fontStyle + '</defs>' +
           '<g transform="translate(' + pad + ' ' + pad + ') rotate(' + rotate + ' ' + (W / 2) + ' ' + (H / 2) + ')">' +
             '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="2.2" opacity="0.92"/>' +
             '<circle cx="' + cx + '" cy="' + cy + '" r="' + rInner + '" fill="none" stroke="' + color + '" stroke-width="1" stroke-dasharray="3 3" opacity="0.55"/>' +
             '<text x="' + cx + '" y="' + (cy - size * 0.19) + '" text-anchor="middle" class="pmTop" font-size="' + fsTop + '" letter-spacing="' + lsTop + '" fill="' + color + '" opacity="0.95">★ ' + escapeXml(state) + ' ★</text>' +
             '<text x="' + cx + '" y="' + cityY + '" text-anchor="middle" dominant-baseline="central" class="pmCity" font-size="' + fsCity + '" fill="' + color + '">' + escapeXml(city) + '</text>' +
             '<line x1="' + (cx - r * 0.42) + '" y1="' + (cy + size * 0.14) + '" x2="' + (cx + r * 0.42) + '" y2="' + (cy + size * 0.14) + '" stroke="' + color + '" stroke-width="1.2" opacity="0.55"/>' +
             '<text x="' + cx + '" y="' + (cy + size * 0.28) + '" text-anchor="middle" class="pmDate" font-size="' + fsDate + '" letter-spacing="' + lsDate + '" fill="' + color + '" opacity="0.95">' + dateTspans + '</text>' +
             '<g opacity="0.92">' + bars + '</g>' +
           '</g>' +
         '</svg>';
  }

  function render(el, opts) {
    if (!el) return;
    el.innerHTML = svg(opts);
  }

  function dataUrl(opts) {
    // External @import is blocked in SVGs loaded via <img>. Skip the font import —
    // the host page must load DM Serif Display + JetBrains Mono in its own <head>;
    // SVG text falls back to Georgia / monospace if those aren't available.
    var safeOpts = Object.assign({}, opts || {}, { embedFont: false });
    var s = svg(safeOpts);
    var b64;
    try {
      b64 = btoa(unescape(encodeURIComponent(s)));
    } catch (_) {
      return "data:image/svg+xml;utf8," + encodeURIComponent(s);
    }
    return "data:image/svg+xml;base64," + b64;
  }

  /* Auto-init for any element with [data-postmark].
     Reads attrs: data-city, data-state, data-date, data-year,
                  data-color, data-size, data-rotate. */
  function autoInit() {
    var els = document.querySelectorAll("[data-postmark]");
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      render(e, {
        city:   e.getAttribute("data-city"),
        state:  e.getAttribute("data-state"),
        date:   e.getAttribute("data-date"),
        year:   e.getAttribute("data-year"),
        color:  e.getAttribute("data-color"),
        size:   e.getAttribute("data-size"),
        rotate: e.getAttribute("data-rotate"),
      });
    }
  }
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", autoInit);
    } else {
      autoInit();
    }
  }

  var api = { svg: svg, render: render, dataUrl: dataUrl };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.Postmark = api;

})(typeof window !== "undefined" ? window : this);
