# 1-install → 4-assets repurposing pipeline (W351)

**Why this doc exists.** Every completed install already produces the raw
material for real, honest marketing — but today only a `Realisation` entry
gets made from it (see `apps/web/src/lib/realisations.ts`, whose entries
already carry `ville`/`region`/`kwc`/`production`/`panneaux`/`resume`/
`photos`). The rest of the value in a field visit evaporates. This is the
checklist that turns one install into four durable assets instead of one.
It changes no code — it is the process every completed install should go
through.

## The checklist (run once per completed install)

1. **Case-study entry** (`apps/web/src/lib/realisations.ts`).
   Add a `Realisation` object: `slug`, `ref`, `ville`/`region`, `kwc`/
   `kwcNum`, `date`, `production`/`productionNum` (from Deye Cloud once
   measured — leave `null` until real data exists, never invent a figure),
   `panneaux`, `onduleur`, `batterie`, `segment`, a short honest `resume`,
   and the `photos` array (real site photos only, per `RealisationPhoto`'s
   `name`/`alt`/`ratio`/`widths`).

2. **Blog retrospective** (`apps/web/src/content/blog/*.md`).
   One markdown post telling the install's story against the existing
   frontmatter schema (`apps/web/src/content.config.ts`: `title`,
   `description`, `pubDate`, `tags`, `author`, `draft`, optional `cover`).
   Link back to the case-study entry from step 1. This is the SEO/organic
   asset — see "the blog scheduler" below for how/when it goes live.

3. **One vertical clip** (9:16, for Instagram/TikTok/WhatsApp Status).
   15–30 s from the same site visit — ideally the install itself or a
   client reaction, per the existing `VideoChantier`/`LiteVideo` facade
   pattern (W346) so it never costs an LCP hit if it lands on-site later.
   Post it, then point its bio link at `/liens` (W350) or the specific
   case-study page.

4. **Proposal-proof photos.**
   A small set of real site photos (panels mounted, meter/app reading,
   client's roof) held in reserve specifically to backfill:
   - the credibility block on the proposal page (WJ13,
     `apps/web/src/pages/proposition/[token].astro`) — already scaffolded
     `pending real content`;
   - the trust placement at the signature step (WJ57, same file).

   Do not wait for a dedicated photo shoot: the visit that produces the
   case-study photos (step 1) is the same visit that should produce these.

## WJ13 / WJ57 acceptance note

`docs/WEB_PLAN.md` should NOT be hand-edited by this task (out of scope for
this lane) — this section is the note for the orchestrator to fold into
that file:

> WJ13 and WJ57's acceptance criteria should read: **"video testimonial
> preferred, photo fallback."** Both tasks already scaffold a testimonial
> slot for the proposal's credibility block (WJ13) and the signature-step
> trust placement (WJ57); this pipeline's step 3 (vertical clip) is what
> supplies the preferred video, and step 4 (proposal-proof photos) is the
> fallback when no usable clip exists yet for a given install. WJ13 is
> already shipped `[x]` with this exact "video slot when WG6 lands, text
> fallback" shape; WJ57 is still open `[ ]` and should be built against the
> same preference order once a testimonial (video or text) exists to place.

## What the blog "scheduler" actually is (verified against source)

There is **no cron job, queue, or scheduled task** anywhere in `apps/web`.
"Scheduler" refers to a simple date-gated publish filter evaluated at
build/request time:

- `apps/web/src/content.config.ts` defines the `blog` collection with a
  required `pubDate` (`z.coerce.date()`) and a `draft` boolean
  (`z.boolean().default(false)`) on every Markdown post under
  `src/content/blog/`.
- `apps/web/src/pages/blog/index.astro` and
  `apps/web/src/pages/blog/[...slug].astro` both filter the collection with
  the same predicate in production:
  `!data.draft && data.pubDate.getTime() <= Date.now()`.

So "scheduling" a post means committing it now with a **future** `pubDate`
and `draft: false` — it simply won't appear on the site (list or direct
slug route) until a rebuild/request happens on or after that date, and
Astro's static-at-build nature means a post scheduled for a date after the
last deploy only actually appears once something (a deploy, or the
site's normal Cloudflare Workers Builds trigger on the next `main` push)
re-runs after that date. There is no automatic "wake up and publish at
midnight" mechanism — if no deploy happens after the `pubDate` passes, the
post stays invisible until the next deploy. Before extending this
mechanism (e.g. a true recurring auto-deploy or a queue), that gap should
be weighed: today, "scheduling" a post is really "pre-writing it and
trusting the next deploy to land after its date."
