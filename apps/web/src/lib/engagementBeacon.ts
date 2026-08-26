/**
 * ANALYT1 (audit item 64, 26/08/2026) — beacon léger de VISIBILITÉ par
 * SECTION sur la page /proposition/[...token].astro.
 *
 * Étend le backend XSAL16 déjà existant (`ShareLink.engagement`,
 * `apps/ventes/public_views.py proposal_engagement`) qui n'avait ENCORE
 * AUCUN appelant côté web (la moitié web du plan WJ n'avait jamais été
 * construite) — ce module EST cette moitié, pas un second pipeline
 * d'analytics : même endpoint public, même forme de corps
 * `{section, seconds}`, plus `visit_id` (ANALYT1, additif, ignoré par un
 * backend antérieur à cette lane).
 *
 * DOCTRINE (Proposify) : une proposition PERDANTE est re-consultée
 * davantage qu'une proposition GAGNANTE — relire la même section sur
 * plusieurs VISITES distinctes est un signal de FRICTION (« ce client
 * hésite, un appel peut débloquer la décision »), jamais un chiffre montré
 * au client, jamais une revendication devant le commercial autre qu'un
 * signal interne (`friction_alert`, lu uniquement côté ERP).
 *
 * PATTERN — same-origin proxy, jamais un appel backend direct (même
 * discipline que `/api/proposition-accept`, `/api/proposition-track`) :
 * ce module poste vers `/api/proposition-engagement` (`pages/api/
 * proposition-engagement.ts`), qui relaie côté serveur vers
 * `{API_BASE}/api/django/public/proposal/<token>/engagement/`.
 *
 * Comme `lib/visite.ts` : logique PURE testable sans DOM/réseau
 * (`buildEngagementBeaconBody`, `cleanEngagementSeconds`,
 * `cleanEngagementSection`, `secondesEnAttente`) + une seule fonction
 * comportementale (`installerBaliseEngagement`, jsdom-testable via
 * injection — `observerFactory`/`fetchFn`/`visitId`), jamais bloquante,
 * jamais un throw visible côté client.
 *
 * APERÇU INTERNE — aucun beacon n'est jamais installé sur le jeton d'aperçu
 * commercial (`cfg.apercuInterne`, même garde que `trackProposalEvent`/
 * `demarrerBalise`) : un aperçu n'est pas une lecture CLIENT à mesurer.
 */

import { creerAccumulateurTempsVisible, genererUuidV4, type VisibleTimeAccumulator } from './visite';

/**
 * Sections suivies — miroir VOLONTAIRE de `_ENGAGEMENT_SECTIONS` côté
 * backend (`apps/ventes/public_views.py`) restreint aux ancres RÉELLEMENT
 * présentes sur la page actuelle (`data-track-section` posé sur chaque
 * `<section>` correspondante) : le fold d'accueil (`hero`), les trois
 * tailles Éco/Recommandé/Max (`tailles`, id `#tailles`), les options
 * sans/avec batterie (`options`, id `#options`), le graphe de production
 * (`graphs`, id `#production`), le bloc économies/financement (`economies`,
 * id `#financing-headline`), le calepinage 3D (`calepinage`, id `#roof3d`),
 * le schéma électrique (`sld`, id `#sld`) et la signature (`signature`, id
 * `#signer`). 'prix'/'etude'/'garanties' du backend restent des clés
 * whitelistées historiques SANS ancre sur la page actuelle — jamais émises
 * ici, jamais retirées côté serveur (comportement des liens existants
 * inchangé).
 */
export const ENGAGEMENT_SECTION_KEYS = [
  'hero', 'tailles', 'options', 'graphs', 'economies', 'calepinage', 'sld', 'signature',
] as const;
export type EngagementSectionKey = (typeof ENGAGEMENT_SECTION_KEYS)[number];

/** Attribut DOM posé sur chaque `<section>` suivie — découplé de son `id` HTML. */
export const ENGAGEMENT_SECTION_ATTR = 'data-track-section';

/** Proxy same-origin (voir `pages/api/proposition-engagement.ts`). */
export const ENGAGEMENT_PROXY_PATH = '/api/proposition-engagement';

/** Délai de débounce avant un flush périodique (page restée ouverte longtemps
 *  sur la même section, sans transition d'intersection). */
export const ENGAGEMENT_FLUSH_DEBOUNCE_MS = 4000;

/** Seuil d'intersection : la section doit occuper ≥ 40 % du viewport pour
 *  compter comme "lue" — même seuil que le `financingIo` WJ9 existant. */
export const ENGAGEMENT_INTERSECTION_THRESHOLD = 0.4;

/** Garde-fou anti-garbage : jamais plus d'une heure envoyée en un seul appel. */
const MAX_SECONDS_PER_BEACON = 3600;

function isEngagementSectionKey(v: unknown): v is EngagementSectionKey {
  return typeof v === 'string' && (ENGAGEMENT_SECTION_KEYS as readonly string[]).includes(v);
}

/** `null` si `v` n'est pas une des sections whitelistées — jamais une section arbitraire. */
export function cleanEngagementSection(v: unknown): EngagementSectionKey | null {
  return isEngagementSectionKey(v) ? v : null;
}

/** Entier de secondes, borné ]0, MAX_SECONDS_PER_BEACON] — 0 pour toute valeur invalide/négative. */
export function cleanEngagementSeconds(v: unknown): number {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return Math.min(Math.round(n), MAX_SECONDS_PER_BEACON);
}

/** `true` si `v` a la forme (anti-garbage minimal, alnum+tiret ≤ 64) d'un identifiant de visite. */
export function isPlausibleVisitId(v: unknown): v is string {
  return typeof v === 'string' && v.length > 0 && v.length <= 64 && /^[A-Za-z0-9-]+$/.test(v);
}

export interface EngagementBeaconBody {
  section: EngagementSectionKey;
  seconds: number;
  visit_id: string;
}

/**
 * Corps PUR d'un beacon de section — `null` quand il n'y a rien d'exploitable
 * à envoyer (section inconnue, 0 seconde, ou `visitId` malformé) : le beacon
 * ne poste alors simplement rien, jamais une erreur.
 */
export function buildEngagementBeaconBody(
  section: unknown,
  seconds: unknown,
  visitId: unknown,
): EngagementBeaconBody | null {
  const cleanSection = cleanEngagementSection(section);
  const cleanSeconds = cleanEngagementSeconds(seconds);
  if (!cleanSection || cleanSeconds <= 0 || !isPlausibleVisitId(visitId)) return null;
  return { section: cleanSection, seconds: cleanSeconds, visit_id: visitId };
}

/**
 * Identifiant de VISITE de cette page-load — Web Crypto si disponible (même
 * générateur que `lib/visite.ts genererUuidV4`), JAMAIS persisté (aucun
 * localStorage/cookie) : un rechargement de page génère un NOUVEL id, ce qui
 * est PRÉCISÉMENT ce qui permet au backend de compter des visites distinctes
 * (ANALYT1) plutôt que de simples ré-entrées dans la même lecture.
 */
export function creerVisitId(randomFn: () => number = Math.random): string {
  return genererUuidV4(randomFn);
}

/** Suivi PUR d'une section : accumule le temps VISIBLE (réutilise l'accumulateur
 *  générique de `lib/visite.ts`) et sait ce qui reste à transmettre. */
export interface SectionTracker {
  key: EngagementSectionKey;
  acc: VisibleTimeAccumulator;
  /** Secondes déjà transmises au backend — un flush n'envoie que le delta. */
  sentSeconds: number;
}

export function creerSuiviSection(
  key: EngagementSectionKey,
  now: () => number = Date.now,
): SectionTracker {
  return { key, acc: creerAccumulateurTempsVisible(now), sentSeconds: 0 };
}

/** Secondes accumulées mais PAS ENCORE transmises pour cette section (jamais négatif). */
export function secondesEnAttente(tracker: SectionTracker): number {
  const total = Math.floor(tracker.acc.totalMs() / 1000);
  return Math.max(0, total - tracker.sentSeconds);
}

// ── Câblage DOM comportemental (jsdom-testable par injection) ──────────────

/** Sous-ensemble minimal d'IntersectionObserver dont dépend ce module. */
export interface EngagementObserverLike {
  observe(el: Element): void;
  disconnect(): void;
}
export interface EngagementObserverEntry {
  target: Element;
  isIntersecting: boolean;
}
export type EngagementObserverFactory = (
  callback: (entries: EngagementObserverEntry[]) => void,
) => EngagementObserverLike;

export interface InstallerBaliseEngagementOptions {
  /** `true` → n'installe RIEN (aperçu commercial interne). */
  apercuInterne?: boolean;
  fetchFn?: typeof fetch;
  /** Racine à interroger pour `[data-track-section]` — repli `document`. */
  root?: ParentNode;
  /** Repli `ENGAGEMENT_FLUSH_DEBOUNCE_MS`. */
  debounceMs?: number;
  /** Fabrique d'observateur injectable — repli `window.IntersectionObserver`. */
  observerFactory?: EngagementObserverFactory;
  /** Identifiant de visite injectable (tests déterministes) — repli `creerVisitId()`. */
  visitId?: string;
}

function defaultObserverFactory(): EngagementObserverFactory | null {
  if (typeof IntersectionObserver === 'undefined') return null;
  return (callback) =>
    new IntersectionObserver(
      (entries) => callback(entries.map((e) => ({ target: e.target, isIntersecting: e.isIntersecting }))),
      { threshold: ENGAGEMENT_INTERSECTION_THRESHOLD },
    );
}

/**
 * Installe le suivi de visibilité par section sur toutes les
 * `[data-track-section]` de `root`. Best-effort strict : sections absentes,
 * IntersectionObserver indisponible (vieux navigateur), `fetch`/
 * `sendBeacon` en échec → rien ne casse jamais la page.
 *
 * Renvoie une fonction de nettoyage (déconnecte l'observateur, retire les
 * listeners) — utilisée par les tests, jamais nécessaire côté page réelle
 * (la page se décharge et l'état disparaît avec elle).
 */
export function installerBaliseEngagement(
  token: string,
  opts: InstallerBaliseEngagementOptions = {},
): (() => void) | undefined {
  if (opts.apercuInterne) return undefined;
  if (typeof document === 'undefined') return undefined;

  const root = opts.root ?? document;
  const elements = Array.from(root.querySelectorAll(`[${ENGAGEMENT_SECTION_ATTR}]`));
  if (elements.length === 0) return undefined;

  const makeObserver = opts.observerFactory ?? defaultObserverFactory();
  if (!makeObserver) return undefined;

  const fetchFn = opts.fetchFn ?? (typeof fetch !== 'undefined' ? fetch : undefined);
  const visitId = opts.visitId ?? creerVisitId();
  const debounceMs = opts.debounceMs ?? ENGAGEMENT_FLUSH_DEBOUNCE_MS;

  const trackers = new Map<EngagementSectionKey, SectionTracker>();
  const intersecting = new Set<EngagementSectionKey>();
  let flushTimer: ReturnType<typeof setTimeout> | undefined;

  function trackerFor(key: EngagementSectionKey): SectionTracker {
    let t = trackers.get(key);
    if (!t) {
      t = creerSuiviSection(key);
      trackers.set(key, t);
    }
    return t;
  }

  function sendOne(tracker: SectionTracker): void {
    const seconds = secondesEnAttente(tracker);
    const body = buildEngagementBeaconBody(tracker.key, seconds, visitId);
    if (!body) return;
    tracker.sentSeconds += body.seconds;
    try {
      const payload = JSON.stringify({ token, ...body });
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        navigator.sendBeacon(ENGAGEMENT_PROXY_PATH, new Blob([payload], { type: 'application/json' }));
      } else if (fetchFn) {
        void fetchFn(ENGAGEMENT_PROXY_PATH, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          keepalive: true,
          body: payload,
        }).catch(() => {
          // Best-effort strict : jamais d'erreur visible.
        });
      }
    } catch {
      // Best-effort strict (ex. Blob indisponible en test).
    }
  }

  function flushNow(): void {
    if (flushTimer !== undefined) {
      clearTimeout(flushTimer);
      flushTimer = undefined;
    }
    trackers.forEach(sendOne);
  }

  function scheduleFlush(): void {
    if (flushTimer !== undefined) return;
    flushTimer = setTimeout(() => {
      flushTimer = undefined;
      trackers.forEach(sendOne);
    }, debounceMs);
  }

  const observer = makeObserver((entries) => {
    for (const entry of entries) {
      const key = cleanEngagementSection(entry.target.getAttribute(ENGAGEMENT_SECTION_ATTR));
      if (!key) continue;
      const tracker = trackerFor(key);
      if (entry.isIntersecting) {
        intersecting.add(key);
        if (typeof document === 'undefined' || document.visibilityState !== 'hidden') {
          tracker.acc.resume();
        }
      } else {
        intersecting.delete(key);
        tracker.acc.pause();
        scheduleFlush();
      }
    }
  });

  elements.forEach((el) => observer.observe(el));

  function onVisibilityChange(): void {
    if (document.visibilityState === 'hidden') {
      trackers.forEach((t) => t.acc.pause());
      flushNow();
    } else {
      intersecting.forEach((key) => trackers.get(key)?.acc.resume());
    }
  }
  document.addEventListener('visibilitychange', onVisibilityChange);
  if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', flushNow);
    window.addEventListener('beforeunload', flushNow);
  }

  return () => {
    observer.disconnect();
    document.removeEventListener('visibilitychange', onVisibilityChange);
    if (typeof window !== 'undefined') {
      window.removeEventListener('pagehide', flushNow);
      window.removeEventListener('beforeunload', flushNow);
    }
    if (flushTimer !== undefined) clearTimeout(flushTimer);
  };
}
