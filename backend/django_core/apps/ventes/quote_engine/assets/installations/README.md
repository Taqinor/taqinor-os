# Installation photo library (quote cover hero)

The quote covers (residential **and** agricole) pick the photo here whose power
is **nearest** the quote's kWc, preferring the same market type. Agricole has no
farm photos yet, so it falls back to a residential / industriel / commercial
photo of similar power.

## How to add photos
Drop **JPEG** files named `<mode>-<kwc>.jpg`:

- `residentiel-5.4.jpg` — a 5.4 kWc residential install
- `industriel-30.jpg` — a 30 kWc commercial/industrial install
- `agricole-10.jpg` — a 10 kWc pumping install (when you have one)

`<mode>` is one of `residentiel`, `industriel`, `commercial`, `agricole`
(optional). `<kwc>` is the system size. The more real photos you add across the
power range, the better each quote's hero matches.

`default.jpg` (no mode/kWc) is the **universal fallback** used when nothing
better matches. It currently duplicates the residential hero so existing quotes
look unchanged.

JPEG only — the cover embeds it as `image/jpeg`.
