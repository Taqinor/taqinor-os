# Quote-engine rendering notes (WeasyPrint gotchas)

The premium quote PDFs (`agricole/`, `residential/`) are rendered with **WeasyPrint**.
WeasyPrint's **flexbox support is incomplete** and has bitten this engine repeatedly.
Read this before touching any `*.py` that emits card/grid layout CSS.

## 1. Do NOT use `display:flex` for a row of equal-height cards followed by another block

**Symptom:** the next block (e.g. a KPI grid, a message row) renders **on top of**
the flex row — "cards on top of each other". WeasyPrint computes a flex
container's *flow height* (used to place the following sibling) **smaller than the
height its flex children actually render at** — a roughly constant ~25pt undershoot.
Pinning `height`/`min-height` on the flex container does **not** fix it (WeasyPrint
sizes the flex container to content anyway and still under-reports flow height).

**Symptom 2 (horizontal):** a flex column with `white-space:nowrap` content (a big
value like `7,8 kWc`) **overflows its `flex:1 1 0` box** and slides under the
neighbouring column — the value gets clipped/hidden.

**Fix — use a CSS table instead of flex for these card rows:**
```css
.row   { display:table; width:100%; }          /* + table-layout:fixed for equal cols */
.cell  { display:table-cell; vertical-align:middle; }  /* or top */
.gap   { display:table-cell; width:14px; }      /* spacer cell = the "gap" */
```
```html
<div class="row"><div class="cell">…</div><div class="gap"></div><div class="cell">…</div></div>
```
Table cells auto-equalise height **and** report correct flow height, and
`table-layout:fixed` gives deterministic column widths so nothing overflows.
`border-radius`, borders and backgrounds render fine on table cells in WeasyPrint.
Real fixes applied this way: `agricole/cover.py` `.a1-hook` (p1 hero hook over the
KPI grid) and `agricole/study.py` `.a2-cols` (p2 chain value under the callout).

## 2. flex `gap` collapses in narrow rows

`gap:` on a flex row is **not reliably honoured** — especially combined with
`margin-left:auto`. Adjacent items butt together (e.g. "Signature+ acompte 30%",
"7,8 kWc​de champ solaire"). **Don't rely on flex `gap` for separation:** use an
explicit `margin-left` on the right-hand item, or stack the two pieces as block
elements. Fixed this way in `agricole/economics_page.py` (`.a4-step`) and
`agricole/cover.py` (`.a1-bign-t`).

## 3. Python version: render/verify on **3.11**, never local 3.13 / CI 3.12

Prod generates PDFs on **Python 3.11.11** (`django_core` + `fastapi_ia` images). A
backslash inside an f-string expression is legal on 3.12+ but a **`SyntaxError` on
3.11** — it crashed the live agricole renderer (silent fallback to the legacy
one-page PDF). CI is now pinned to 3.11 with a `compileall` guard (see
`.github/workflows/ci.yml`). When verifying a PDF locally on Windows (WeasyPrint
won't import natively), render in the prod image, not local Python:
```
docker run --rm -v <repo>/backend/django_core:/app -v <tmp>:/repro \
  erp-agentique-django_core:latest python /repro/repro.py
```
then view the PDF→PNG with PyMuPDF (`fitz`, installed locally).

## How to catch overlaps before shipping

Render the PDF, then scan each page for colliding card rectangles with PyMuPDF
(`page.get_drawings()` → pairwise `Rect & Rect` intersection). A genuine card
collision shows an intersection that is a thin band (small relative to both rects)
— filter out nested background rects. This is how the p1/p2 overlaps were found
and confirmed fixed (degraded + full-data scenarios both scan clean).
