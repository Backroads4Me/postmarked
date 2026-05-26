**3 different border treatments**:

1. **Airmail edge border** on the “Currently at” card
2. **Perforated / ticket edge** on the updates card
3. **Postage-stamp edge** for small decorative stamp elements

## 1) Airmail border

The **easiest and most robust** way is:

- an **outer wrapper** with the red/blue stripe pattern as its background
- a little **padding** to create the border thickness
- an **inner panel** with your cream paper background

### HTML

```html
<div class="airmail-frame">
  <section class="airmail-card">
    <!-- your content -->
  </section>
</div>
```

### CSS

```css
:root {
  --paper: #f6f0df;
  --paper-2: #efe5cc;
  --ink: #142b5f;
  --accent-red: #d85a43;
  --accent-blue: #6f90b7;
  --line: #d8c8a8;
}

.airmail-frame {
  padding: 10px; /* thickness of border */
  border-radius: 18px;
  background: repeating-linear-gradient(
    -45deg,
    var(--accent-red) 0 10px,
    var(--accent-red) 10px 10px,
    #f3ebd7 10px 20px,
    var(--accent-blue) 20px 30px,
    #f3ebd7 30px 40px
  );
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

.airmail-card {
  background: linear-gradient(180deg, #f9f4e6, var(--paper));
  border-radius: 12px;
  padding: 2rem;
  border: 1px solid rgba(216, 200, 168, 0.8);
}
```

### Why this is the best approach

This is much easier than trying to “draw only the border” with masks.
You just let the outer wrapper be the decorative edge.

---

## 2) Perforated / ticket border

For the update card, the scalloped “torn stamp / ticket” edge can be faked with **radial gradients** placed on the left and right sides.

### HTML

```html
<article class="perforated-card">
  <!-- update content -->
</article>
```

### CSS

```css
.perforated-card {
  position: relative;
  background: linear-gradient(180deg, #f9f4e6, var(--paper));
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 2rem;
  overflow: visible;
}

/* cutout circles on left + right */
.perforated-card::before,
.perforated-card::after {
  content: "";
  position: absolute;
  top: 18px;
  bottom: 18px;
  width: 16px;
  pointer-events: none;
  background-size: 16px 24px;
  background-repeat: repeat-y;
}

/* left side perforation */
.perforated-card::before {
  left: -8px;
  background-image: radial-gradient(
    circle at 8px 12px,
    var(--page-bg, #f3ead4) 0 8px,
    transparent 8.5px
  );
}

/* right side perforation */
.perforated-card::after {
  right: -8px;
  background-image: radial-gradient(
    circle at 8px 12px,
    var(--page-bg, #f3ead4) 0 8px,
    transparent 8.5px
  );
}
```

### What this does

It places page-colored circles overlapping the card edge, which makes the border look perforated.

If you want **smaller perforations**, reduce:

- `width`
- `background-size`
- circle radius values

---

## 3) Postage stamp border

For a small decorative “stamp” block, you can use the same perforation idea but on **all four sides**.
This is where **SVG becomes a really good option** if you want it crisp and easy to control.

### Easy CSS version

```css
.stamp {
  position: relative;
  display: inline-block;
  padding: 1rem;
  background: #eadfc3;
  border: 1px solid #d1bf98;
}

.stamp::before {
  content: "";
  position: absolute;
  inset: -6px;
  background: radial-gradient(
      circle at 6px 6px,
      transparent 0 5px,
      #f3ead4 5.5px
    )
    0 0 / 18px 18px repeat;
  pointer-events: none;
}
```

That gives you a postage-ish perforated feel, though not as perfect as SVG.

---

# My recommendation: use **CSS for layout borders**, SVG for specialty shapes

If I were building your site, I’d do this:

## Use CSS for:

- airmail wrapper border
- perforated timeline card edges
- dashed dividers
- subtle paper texture / lines

## Use SVG for:

- red circular stamp marks
- wavy postal cancellation lines
- small postage stamp decorative blocks

That gives you:

- simple code
- crisp rendering
- easy reuse as components

---

# Example: full “airmail card” structure

This is probably closest to the big top card in your mockup.

### HTML

```html
<div class="airmail-frame">
  <section class="location-card">
    <div class="location-card__header">
      <span class="eyebrow">Currently at</span>
      <h2>Bayfield, WI</h2>
      <p>Apostle Islands Area Campground</p>
    </div>

    <div class="location-card__body">
      <div>
        <div class="meta-label">Arrived</div>
        <div>Sat, May 23</div>
      </div>
      <div>
        <div class="meta-label">Staying</div>
        <div>4 nights</div>
      </div>
    </div>
  </section>
</div>
```

### CSS

```css
.location-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0)),
    linear-gradient(180deg, #f8f3e5, #f3ead6);
  border: 1px solid rgba(216, 200, 168, 0.7);
  border-radius: 12px;
  padding: 2rem;
}

.location-card__header h2 {
  margin: 0 0 0.25rem;
  font-family: "Playfair Display", Georgia, serif;
  font-size: 3rem;
  color: var(--ink);
}

.location-card__header p {
  margin: 0;
  color: #8b7c60;
}

.eyebrow,
.meta-label {
  font-family: "IBM Plex Mono", monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.8rem;
  color: #8c7d65;
}

.location-card__body {
  display: flex;
  gap: 2rem;
  margin-top: 1.5rem;
  padding-top: 1.25rem;
  border-top: 1px dashed #d8c8a8;
}
```

---

# If you want the border on only the outside edge

Sometimes you only want the airmail stripe at the **very edge**, not behind the rounded corners weirdly.

In that case:

```css
.airmail-frame {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  padding: 10px;
  background: repeating-linear-gradient(
    -45deg,
    #d85a43 0 10px,
    #d85a43 10px 10px,
    #f3ebd7 10px 20px,
    #6f90b7 20px 30px,
    #f3ebd7 30px 40px
  );
}
```

`overflow: hidden` is key there.

---

# If you’re using Tailwind

This is still easiest as:

- a wrapper div for the border
- a child div for the card
- a custom CSS class for the repeating gradient

So I would not try to do this entirely with utility classes.
I’d create small reusable component classes like:

- `.airmail-frame`
- `.perforated-card`
- `.postmark`
- `.stamp-block`

---

# Best practical approach for your site

If I were implementing your actual design, I’d do:

### Component set

- **`PaperCard`** → plain cream card
- **`AirmailCard`** → outer stripe wrapper + inner paper panel
- **`PerforatedCard`** → paper card with ticket edges
- **`Postmark`** → inline SVG
- **`CancelLines`** → inline SVG
- **`StampBadge`** → small decorative stamp in corner

That keeps the design system clean and consistent.
