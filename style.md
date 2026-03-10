# Phoenix Import Style Guide

## Colours

Standard page styling uses the usual **black/grey text on white backgrounds**.

When adding coloured elements (headers, buttons, accents, etc.), use the brand colours:

| Name       | Hex       | Usage                              |
|------------|-----------|------------------------------------|
| Purple     | `#68437B` | Headers, coloured backgrounds      |
| Pink       | `#ca427e` | Buttons, accents, CTAs             |
| Pink hover | `#b33a6f` | Button hover states                |

Use **white text** on these coloured backgrounds for contrast.

## Typography

- **Font family:** `Calibri, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Calibri is the primary brand font; the system font stack provides clean fallbacks on platforms where Calibri is unavailable.
- Use this font stack for all body text, headings, and UI elements.

## Logo

- The logo file is `logo.png` (in the root directory), referenced as `src="logo.png"`.
- It should appear in the header, aligned to the right.
- Wrap it in an anchor linking back to `index.html` so users can always return to the index:

```html
<a href="index.html" style="margin-left:auto;line-height:0;">
  <img src="logo.png" alt="Phoenix Import">
</a>
```

- `margin-left:auto` on the **anchor** (not the img) pushes it to the right in the flex header.
- `line-height:0` removes the small gap that appears below inline images inside anchors.
- If the img has an inline `height` style, keep it on the img; keep `margin-left:auto` on the anchor.
