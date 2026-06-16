# Website build plan (apps/web)

## BUILD QUEUE
<!-- One task per line, plain language. Example: [ ] Replace the hero subtitle on /résidentiel with the new copy -->
[x] Add an HTML comment reading <!-- autopilot shakedown 2026-06-16 --> to the top of the homepage layout in apps/web, so a deploy can be confirmed from page source. Trivial and invisible to visitors; remove it on the next run.

## DONE LOG
2026-06-16 — Added `<!-- autopilot shakedown 2026-06-16 -->` at the top of the homepage markup (apps/web/src/pages/index.astro); renders into page source, invisible to visitors. Astro build verified.
