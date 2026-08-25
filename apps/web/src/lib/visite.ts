/**
 * LANE T-WEB — Balise de visite SITE ENTIER : empreinte d'appareil anonyme +
 * durée cumulée par page, postée en best-effort vers le backend via le proxy
 * same-origin `pages/api/visite.ts`.
 *
 * Contrat backend (lane parallèle, verbatim) :
 *   POST /api/django/crm/public/visite/
 *     { appareil_id, page, duree_s, fin, langue } → { ok: true }
 *
 * AUTH — même discipline que tous les autres proxies same-origin de ce
 * dossier (`capture-lead.ts`, `funnel-beacon.ts`, `proposition-track.ts`,
 * `questionnaire-repondre.ts`) : `isSameOriginRequest`/`crossSiteRejection`
 * (`lib/lead.ts`) + rate-limit par IP (`lib/rateLimit.ts`), jamais de secret
 * exposé au navigateur. `/api/django/crm/public/visite/` suit la même
 * convention d'URL PUBLIQUE que `/api/django/crm/public/questionnaire/<token>/`
 * (`questionnaireEndpoint`, `lib/questionnaire.ts`) — un appel serveur direct
 * vers l'API_BASE, sans le secret statique `LEAD_WEBHOOK_SECRET` réservé au
 * webhook de CAPTURE DE LEAD (`apps/crm/webhooks.py`, un tout autre récepteur
 * qui, lui, CRÉE/MET À JOUR un lead CRM — cette balise ne fait ni l'un ni
 * l'autre). Voir `pages/api/visite.ts` pour le relais.
 *
 * HARD PRIVACY CONTRACT (même discipline que `lib/funnelBeacon.ts`) : aucune
 * PII — `appareil_id` est un UUID v4 généré côté navigateur, stocké en
 * localStorage SAME-ORIGIN (jamais un cookie tiers), jamais dérivé d'une
 * donnée de contact. `page` est un chemin (jamais une query string ni un
 * fragment), `duree_s` un entier cumulé borné, `fin` un booléen (dernier
 * envoi avant fermeture/navigation).
 *
 * CONSENTEMENT (WB29/WB30/WB31, `components/ConsentBanner.astro`) — cette
 * balise est de la MÊME famille « mesure anonyme d'audience » déjà gouvernée
 * par le signal `tq_consent` (localStorage) : elle ne démarre que si le
 * consentement est déjà `'granted'`, ou dès qu'il le devient (réagit à
 * `tq:consent-change`, exactement comme WB29/WB30) — jamais avant, jamais si
 * `'denied'`.
 *
 * APERÇU INTERNE — aucune balise n'est jamais installée quand la page est un
 * aperçu commercial interne (jeton interne `apercu_interne`, proposition
 * `[...token].astro`, ou son équivalent `interne` du questionnaire
 * `[token].astro`) : ce n'est pas une visite CLIENT à mesurer.
 */

export const VISITE_PROXY_PATH = '/api/visite';

const APPAREIL_ID_KEY = 'tq_appareil';
const HEARTBEAT_MS = 20_000;
const MAX_DUREE_S = 24 * 3600; // garde-fou anti-garbage : jamais plus d'un jour cumulé.

export const VISITE_LANGUES = ['fr', 'en', 'ar'] as const;
export type VisiteLangue = (typeof VISITE_LANGUES)[number];

function isEnum<T extends string>(v: unknown, allowed: readonly T[]): v is T {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v);
}

/** UUID v4 — Web Crypto si disponible (navigateur/Worker/Node ≥ 19), repli RFC4122 minimal sinon. */
export function genererUuidV4(randomFn: () => number = Math.random): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (typeof c?.randomUUID === 'function') return c.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = Math.floor(randomFn() * 16) & 0xf;
    const v = ch === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** `true` si `v` a la forme d'un UUID (peu importe la version) — anti-garbage minimal. */
export function isPlausibleUuid(v: unknown): v is string {
  return typeof v === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}

/** Sous-ensemble de `Storage` dont dépend `appareilId` — permet l'injection en test. */
export type SimpleStorage = Pick<Storage, 'getItem' | 'setItem'>;

function safeLocalStorage(): SimpleStorage | undefined {
  try {
    return typeof localStorage !== 'undefined' ? localStorage : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Identifiant d'appareil ANONYME, stable par navigateur (localStorage
 * SAME-ORIGIN, jamais un cookie tiers, jamais dérivé d'une donnée de
 * contact) : généré une seule fois puis relu. `''` si le stockage est
 * indisponible (mode privé strict, contexte hors DOM…) — jamais bloquant,
 * jamais un throw.
 */
export function appareilId(storage: SimpleStorage | undefined = safeLocalStorage()): string {
  if (!storage) return '';
  try {
    const existing = storage.getItem(APPAREIL_ID_KEY);
    if (isPlausibleUuid(existing)) return existing as string;
    const fresh = genererUuidV4();
    storage.setItem(APPAREIL_ID_KEY, fresh);
    return fresh;
  } catch {
    return '';
  }
}

/** Chemin sûr : commence par "/", jamais de query/fragment (miroir `funnelBeacon.ts` `cleanPath`). */
export function cleanVisitePage(v: unknown): string {
  const raw = typeof v === 'string' ? v.trim().slice(0, 200) : '';
  if (!raw.startsWith('/')) return '/';
  return raw.split('?')[0].split('#')[0] || '/';
}

/** Entier de secondes cumulées, borné [0, MAX_DUREE_S] — jamais négatif, jamais absurde. */
export function cleanDureeS(v: unknown): number {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return Math.min(Math.round(n), MAX_DUREE_S);
}

export interface VisiteBeaconBody {
  appareil_id: string;
  page: string;
  duree_s: number;
  fin: boolean;
  langue: VisiteLangue;
}

/**
 * Construction PURE du corps du beacon — testable sans DOM. `page`/`dureeS`/
 * `langue` acceptent `unknown` en entrée (partagée entre l'appel « de
 * confiance » de `demarrerBalise` et la validation anti-garbage d'un corps
 * REÇU par le proxy, `validateVisiteBody` ci-dessous) : chaque champ est
 * nettoyé/bordé, jamais un throw sur une forme inattendue.
 */
export function buildVisiteBeaconBody(
  appareilIdValue: string,
  page: unknown,
  dureeS: unknown,
  fin: boolean,
  langue: unknown,
): VisiteBeaconBody {
  return {
    appareil_id: typeof appareilIdValue === 'string' ? appareilIdValue : '',
    page: cleanVisitePage(page),
    duree_s: cleanDureeS(dureeS),
    fin: fin === true,
    langue: isEnum(langue, VISITE_LANGUES) ? langue : 'fr',
  };
}

/**
 * Validation PURE du corps reçu par le proxy `pages/api/visite.ts` — même
 * discipline anti-garbage que `funnelBeacon.ts` `validateBeaconEvent` :
 * `null` quand la forme est inexploitable (aucun `appareil_id` UUID
 * plausible), sinon un objet nettoyé prêt à relayer au backend.
 */
export function validateVisiteBody(body: unknown): VisiteBeaconBody | null {
  const b = (body ?? {}) as Record<string, unknown>;
  const appareilIdRaw = typeof b.appareil_id === 'string' ? b.appareil_id : '';
  if (!isPlausibleUuid(appareilIdRaw)) return null;
  return buildVisiteBeaconBody(appareilIdRaw, b.page, b.duree_s, b.fin === true, b.langue);
}

export interface DemarrerBaliseOptions {
  /** Langue de la page (fr/en/ar) — déjà résolue côté page, jamais devinée ici. */
  langue?: VisiteLangue;
  /** `true` → n'installe RIEN (aperçu interne commercial). */
  apercuInterne?: boolean;
  fetchFn?: typeof fetch;
  intervalMs?: number;
  storage?: SimpleStorage;
}

/**
 * Démarre la balise de visite pour la page courante : un premier envoi
 * immédiat (`duree_s=0, fin=false`), un battement toutes les ~20 s (durée
 * cumulée depuis le démarrage), et un dernier envoi `fin:true` via
 * `navigator.sendBeacon` au `pagehide` (repli `fetch keepalive` si
 * indisponible). Best-effort strict : aucune erreur visible, jamais
 * bloquant, jamais réessayé.
 *
 * No-op complet si `apercuInterne`, si `window`/`document` sont absents (SSR,
 * environnement de test sans DOM), si le stockage d'appareil est
 * indisponible, ou tant que le consentement `tq_consent` n'a jamais été
 * accordé (voir `ConsentBanner.astro`, WB29/WB30/WB31) — démarre dès qu'il
 * l'est, via `tq:consent-change`.
 */
export function demarrerBalise(page: string, opts: DemarrerBaliseOptions = {}): void {
  if (opts.apercuInterne) return;
  if (typeof window === 'undefined' || typeof document === 'undefined') return;

  const fetchFn = opts.fetchFn ?? (typeof fetch !== 'undefined' ? fetch : undefined);
  if (!fetchFn) return;

  const id = appareilId(opts.storage);
  if (!id) return; // Stockage indisponible : rien à corréler, on n'envoie rien.

  const langue = opts.langue ?? 'fr';
  const startedAt = Date.now();
  let sentFinal = false;
  let started = false;

  function envoyer(fin: boolean): void {
    const dureeS = (Date.now() - startedAt) / 1000;
    const body = buildVisiteBeaconBody(id, page, dureeS, fin, langue);
    try {
      if (fin && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        navigator.sendBeacon(VISITE_PROXY_PATH, new Blob([JSON.stringify(body)], { type: 'application/json' }));
      } else {
        void fetchFn!(VISITE_PROXY_PATH, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          keepalive: true,
          body: JSON.stringify(body),
        }).catch(() => {
          // Best-effort strict : jamais d'erreur visible.
        });
      }
    } catch {
      // Best-effort strict : jamais d'erreur visible (ex. Blob absent en test).
    }
  }

  function envoyerFinal(): void {
    if (sentFinal) return;
    sentFinal = true;
    envoyer(true);
  }

  function demarrer(): void {
    if (started) return; // idempotent — un second appel (ex. tq:consent-change tardif) ne redémarre pas deux battements.
    started = true;
    envoyer(false);
    window.setInterval(() => envoyer(false), opts.intervalMs ?? HEARTBEAT_MS);
    window.addEventListener('pagehide', envoyerFinal);
    window.addEventListener('beforeunload', envoyerFinal);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') envoyer(false);
    });
  }

  // Gate consentement — même signal que WB29/WB30 (ConsentBanner.astro) :
  // 'granted' → démarre tout de suite ; absent → attend tq:consent-change ;
  // 'denied' → ne démarre jamais.
  try {
    const consent = localStorage.getItem('tq_consent');
    if (consent === 'granted') {
      demarrer();
    } else if (consent !== 'denied') {
      window.addEventListener(
        'tq:consent-change',
        (e) => {
          const detail = (e as CustomEvent<{ value?: string }>).detail;
          if (detail?.value === 'granted') demarrer();
        },
        { once: true },
      );
    }
  } catch {
    // localStorage indisponible pour lire le consentement : par prudence, on ne démarre rien.
  }
}
