/**
 * LANE T-WEB — Balise de visite SITE ENTIER : empreinte d'appareil anonyme +
 * durée cumulée par page, postée en best-effort vers le backend via le proxy
 * same-origin `pages/api/visite.ts`.
 *
 * Contrat backend (lane parallèle, verbatim) :
 *   POST /api/django/crm/public/visite/
 *     { appareil_id, page, duree_s, fin, langue } → { ok: true }
 *
 * AUTH — ENTRÉE (navigateur → proxy) : même discipline que tous les autres
 * proxies same-origin de ce dossier (`capture-lead.ts`, `funnel-beacon.ts`,
 * `proposition-track.ts`, `questionnaire-repondre.ts`) :
 * `isSameOriginRequest`/`crossSiteRejection` (`lib/lead.ts`) + rate-limit par
 * IP (`lib/rateLimit.ts`), jamais de secret exposé au navigateur.
 *
 * AUTH — SORTIE (proxy → backend, recalage porte finale 25/08, décision
 * orchestrateur) : contrairement à un simple relais public,
 * `/api/django/crm/public/visite/` EXIGE la même auth webhook que la capture
 * de lead (`X-Webhook-Secret` = `LEAD_WEBHOOK_SECRET` du Worker =
 * `WEBSITE_LEAD_WEBHOOK_SECRET` côté Django, `hmac.compare_digest`, refus
 * 401) — ces visites alimentent des alertes « concurrent » envoyées à la
 * direction, un endpoint non signé serait empoisonnable par de fausses
 * visites. Secret absent du Worker → le relais est simplement sauté (la
 * balise reste best-effort, jamais bloquant). Voir `pages/api/visite.ts` pour
 * le relais exact.
 *
 * HARD PRIVACY CONTRACT (même discipline que `lib/funnelBeacon.ts`) : aucune
 * PII — `appareil_id` est un UUID v4 généré côté navigateur, stocké en
 * localStorage + cookie FIRST-PARTY partagé avec l'ERP (api.taqinor.ma),
 * jamais un cookie tiers, jamais dérivé d'une donnée de contact. Le cookie
 * (`Domain=taqinor.ma`, voir `domaineCookiePartage` ci-dessous) existe en
 * plus du localStorage pour DEUX raisons : (1) le rendu SERVEUR de
 * `/proposition/<token>` ne voit jamais le localStorage du navigateur — seul
 * un cookie voyage sur la requête SSR ; (2) l'ERP (`api.taqinor.ma`) pose
 * lui-même ce cookie pour marquer un appareil « équipe » (QJ-EQUIPE) —
 * partager le domaine permet au site public de RECONNAÎTRE automatiquement
 * les appareils de l'équipe sans action manuelle (voir `equipe.astro`).
 * `page` est un chemin (jamais une query string ni un fragment), `duree_s`
 * un entier cumulé borné, `fin` un booléen (dernier envoi avant
 * fermeture/navigation).
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

/**
 * Hôte canonique du site — miroir de `site: 'https://taqinor.ma'` dans
 * `astro.config.mjs` (racine `apps/web/`). Ce fichier de config n'est PAS
 * importé ici : c'est l'entrée de build Astro elle-même (side-effecting,
 * imports lourds `astro/config`/adaptateur Cloudflare), jamais un module
 * pensé pour être réutilisé ailleurs — aucune autre constante `SITE_URL` ni
 * `lib/site*.ts` n'existe dans ce dépôt (vérifié). `SITE_HOST` est donc
 * l'UNIQUE source de vérité pour le domaine de cookie partagé ci-dessous —
 * à garder synchronisé avec `astro.config.mjs` si le domaine change un jour.
 */
export const SITE_HOST = 'taqinor.ma';

/**
 * Domaine de cookie à poser pour qu'il soit visible depuis `SITE_HOST` ET
 * ses sous-domaines (dont `api.taqinor.ma`, l'ERP) — PUR, jamais pour un
 * hôte étranger (`localhost`, aperçu `*.workers.dev`…) où `Domain=taqinor.ma`
 * serait de toute façon refusé par le navigateur (RFC 6265 : le domaine d'un
 * cookie doit être un suffixe de l'hôte de la réponse qui le pose). renvoie
 * `undefined` dans ce cas — repli sur un cookie host-only, jamais un throw.
 */
export function domaineCookiePartage(hostname: string, siteHost: string = SITE_HOST): string | undefined {
  if (!hostname || !siteHost) return undefined;
  if (hostname === siteHost || hostname.endsWith(`.${siteHost}`)) return siteHost;
  return undefined;
}

const APPAREIL_COOKIE_MAX_AGE_S = 2 * 365 * 24 * 3600; // 2 ans (63072000) — même durée que tq_equipe.

/**
 * Extrait une valeur de cookie depuis une chaîne "name1=value1; name2=value2"
 * — format COMMUN à `document.cookie` (navigateur) et à l'en-tête HTTP
 * `Cookie:` reçu par un handler serveur (`request.headers.get('cookie')`) :
 * réutilisée par `pages/api/proposition-engagement.ts` (T3) pour lire le
 * même cookie côté proxy same-origin, plutôt que dupliquer un parseur ad hoc.
 * PUR, ne throw jamais ; `undefined` si absent/malformé.
 */
export function lireCookie(cookieHeader: string | null | undefined, name: string): string | undefined {
  if (!cookieHeader) return undefined;
  for (const part of cookieHeader.split(';')) {
    const eq = part.indexOf('=');
    if (eq === -1) continue;
    const key = part.slice(0, eq).trim();
    if (key !== name) continue;
    const raw = part.slice(eq + 1).trim();
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }
  return undefined;
}

/** Attributs d'un cookie posé par `SimpleCookieStore.set` — voir `appareilId`. */
export interface SimpleCookieSetAttrs {
  path: string;
  maxAgeSeconds: number;
  sameSite: 'Lax';
  secure: boolean;
  /** `undefined` → cookie host-only (repli `domaineCookiePartage`). */
  domain?: string;
}

/** Sous-ensemble minimal d'un magasin de cookies dont dépend `appareilId` — permet l'injection en test. */
export interface SimpleCookieStore {
  get(name: string): string | undefined;
  set(name: string, value: string, attrs: SimpleCookieSetAttrs): void;
}

/** Sérialise `document.cookie = …` — PUR, testable sans DOM (voir `SimpleCookieStore` par défaut ci-dessous). */
export function serialiserCookie(name: string, value: string, attrs: SimpleCookieSetAttrs): string {
  const parts = [
    `${name}=${encodeURIComponent(value)}`,
    `Path=${attrs.path}`,
    `Max-Age=${attrs.maxAgeSeconds}`,
    `SameSite=${attrs.sameSite}`,
  ];
  if (attrs.secure) parts.push('Secure');
  if (attrs.domain) parts.push(`Domain=${attrs.domain}`);
  return parts.join('; ');
}

/** Implémentation par défaut de `SimpleCookieStore` sur `document.cookie` — `undefined` hors DOM (SSR/tests sans jsdom). */
function safeDocumentCookieStore(): SimpleCookieStore | undefined {
  if (typeof document === 'undefined') return undefined;
  return {
    get(name) {
      try {
        return lireCookie(document.cookie, name);
      } catch {
        return undefined;
      }
    },
    set(name, value, attrs) {
      try {
        document.cookie = serialiserCookie(name, value, attrs);
      } catch {
        // Best-effort strict : jamais bloquant (ex. document.cookie inaccessible).
      }
    },
  };
}

function cookieAttrsPartages(): SimpleCookieSetAttrs {
  const hostname = typeof window !== 'undefined' && window.location ? window.location.hostname : '';
  return {
    path: '/',
    maxAgeSeconds: APPAREIL_COOKIE_MAX_AGE_S,
    sameSite: 'Lax',
    secure: true,
    domain: domaineCookiePartage(hostname),
  };
}

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
 * Identifiant d'appareil ANONYME, stable par navigateur (localStorage +
 * cookie first-party partagé avec l'ERP, jamais un cookie tiers, jamais
 * dérivé d'une donnée de contact) : généré une seule fois puis relu.
 * `''` si le stockage local est indisponible (mode privé strict, contexte
 * hors DOM…) — jamais bloquant, jamais un throw. Le cookie n'est qu'un MIROIR
 * partagé avec le SSR/l'ERP ; sans localStorage utilisable, rien n'est
 * considéré stable et la fonction abandonne (même contrat qu'avant l'ajout
 * du cookie — voir le docstring du module pour le POURQUOI du cookie).
 *
 * Ordre : (1) cookie `tq_appareil` plausible → source de vérité, miroir en
 * localStorage si absent/différent ; (2) sinon localStorage plausible → pose
 * le cookie ; (3) sinon génère un nouvel uuid → pose les deux. Si
 * l'écriture en localStorage échoue à une étape où elle est nécessaire, la
 * fonction redescend `''` (storage cassé = rien de stable à corréler),
 * même si le cookie a par ailleurs pu être écrit avec succès.
 */
export function appareilId(
  storage: SimpleStorage | undefined = safeLocalStorage(),
  cookies: SimpleCookieStore | undefined = safeDocumentCookieStore(),
): string {
  if (!storage) return '';

  let existing: string | null;
  try {
    existing = storage.getItem(APPAREIL_ID_KEY);
  } catch {
    return '';
  }

  let fromCookie: string | undefined;
  try {
    fromCookie = cookies?.get(APPAREIL_ID_KEY);
  } catch {
    fromCookie = undefined;
  }

  if (isPlausibleUuid(fromCookie)) {
    if (fromCookie !== existing) {
      try {
        storage.setItem(APPAREIL_ID_KEY, fromCookie);
      } catch {
        return ''; // Storage cassé en écriture : rien de fiable à retourner.
      }
    }
    return fromCookie;
  }

  if (isPlausibleUuid(existing)) {
    try {
      cookies?.set(APPAREIL_ID_KEY, existing, cookieAttrsPartages());
    } catch {
      // Best-effort strict : le cookie est un miroir, jamais bloquant.
    }
    return existing;
  }

  const fresh = genererUuidV4();
  try {
    storage.setItem(APPAREIL_ID_KEY, fresh);
  } catch {
    return ''; // Storage cassé en écriture : rien de fiable à retourner.
  }
  try {
    cookies?.set(APPAREIL_ID_KEY, fresh, cookieAttrsPartages());
  } catch {
    // Best-effort strict : le cookie est un miroir, jamais bloquant.
  }
  return fresh;
}

// Correctif F3#7 — même doctrine que `suffixe_jeton` côté backend
// (`apps/crm/visites.py`) : un segment de chemin qui RESSEMBLE à un jeton
// porteur (> 24 caractères — les jetons publics font 43+ caractères, jamais
// un slug décoratif) est réduit à ses 6 derniers caractères. Sans ce
// masquage, `location.pathname` des pages `/proposition/<slug>/<token>/` et
// `/questionnaire/<token>/` embarquait le jeton COMPLET dans `page`, persisté
// en base (`contexte`, MAX 200) et réémis dans le corps des alertes envoyées
// aux commerciaux/à la direction.
const MAX_SEGMENT_CLAIR = 24;
const SUFFIXE_JETON_LEN = 6;

function masquerSegmentsJetons(path: string): string {
  return path
    .split('/')
    .map((seg) => (seg.length > MAX_SEGMENT_CLAIR ? `…${seg.slice(-SUFFIXE_JETON_LEN)}` : seg))
    .join('/');
}

/**
 * Chemin sûr : commence par "/", jamais de query/fragment (miroir
 * `funnelBeacon.ts` `cleanPath`), et masque tout segment-jeton — voir
 * `masquerSegmentsJetons` (F3#7).
 */
export function cleanVisitePage(v: unknown): string {
  const raw = typeof v === 'string' ? v.trim().slice(0, 200) : '';
  if (!raw.startsWith('/')) return '/';
  const stripped = raw.split('?')[0].split('#')[0] || '/';
  return masquerSegmentsJetons(stripped);
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

/**
 * Accumulateur PUR de temps VISIBLE (F3#9) — ne compte que les intervalles où
 * `document.visibilityState === 'visible'`, jamais le temps mural passé
 * onglet masqué ou page restaurée depuis le bfcache. Horloge injectable —
 * testable sans DOM.
 */
export interface VisibleTimeAccumulator {
  /** Page devenue visible (ou déjà visible au démarrage) — reprend le cumul. */
  resume(): void;
  /** Page masquée/quittée — fige le cumul au temps réellement visible écoulé. */
  pause(): void;
  /** Total cumulé en millisecondes, segment visible en cours inclus. */
  totalMs(): number;
  /** Repli complet à zéro — jamais le temps mural (réarmement bfcache). */
  reset(): void;
}

export function creerAccumulateurTempsVisible(now: () => number = Date.now): VisibleTimeAccumulator {
  let accumulatedMs = 0;
  let visibleSince: number | null = null;
  return {
    resume() {
      if (visibleSince === null) visibleSince = now();
    },
    pause() {
      if (visibleSince !== null) {
        accumulatedMs += now() - visibleSince;
        visibleSince = null;
      }
    },
    totalMs() {
      return visibleSince === null ? accumulatedMs : accumulatedMs + (now() - visibleSince);
    },
    reset() {
      accumulatedMs = 0;
      visibleSince = null;
    },
  };
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
 * VISIBLE cumulée depuis le démarrage — F3#9, jamais le temps mural), et un
 * dernier envoi `fin:true` via `navigator.sendBeacon` au `pagehide` (repli
 * `fetch keepalive` si indisponible). Best-effort strict : aucune erreur
 * visible, jamais bloquant, jamais réessayé.
 *
 * F3#9 — le cumul n'avance QUE quand `document.visibilityState === 'visible'`
 * (`creerAccumulateurTempsVisible`) : un onglet masqué des heures ne gonfle
 * plus `duree_s`. L'id d'intervalle est conservé et annulé au `pagehide` (via
 * `envoyerFinal`) ; une restauration bfcache (`pageshow` avec
 * `event.persisted`) réarme proprement — remet `sentFinal` à `false`,
 * RÉINITIALISE le cumul à zéro (jamais une reprise depuis l'horodatage
 * mural d'origine) et relance un battement frais.
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

  const langue = opts.langue ?? 'fr';
  const acc = creerAccumulateurTempsVisible();
  let sentFinal = false;
  let started = false;
  let intervalId: ReturnType<typeof setInterval> | undefined;
  // M2 (correctif adversarial, cookie posé sans consentement) — calculé
  // SEULEMENT dans demarrer() ci-dessous, jamais ici : depuis T1,
  // appareilId() écrit un cookie 2 ans (en plus du localStorage), et le
  // contrat CONSENTEMENT de ce module (voir docstring plus haut) interdit
  // toute écriture avant que le consentement soit accordé.
  let id = '';

  function envoyer(fin: boolean): void {
    const dureeS = acc.totalMs() / 1000;
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

  function annulerBattement(): void {
    if (intervalId !== undefined) {
      clearInterval(intervalId);
      intervalId = undefined;
    }
  }

  function demarrerBattement(): void {
    envoyer(false);
    intervalId = setInterval(() => envoyer(false), opts.intervalMs ?? HEARTBEAT_MS);
  }

  function envoyerFinal(): void {
    if (sentFinal) return;
    sentFinal = true;
    acc.pause();
    annulerBattement();
    envoyer(true);
  }

  function demarrer(): void {
    if (started) return; // idempotent — un second appel (ex. tq:consent-change tardif) ne redémarre pas deux battements.
    // M2 — appareilId() (cookie 2 ans + localStorage, T1) n'est calculé QU'ICI,
    // dans le seul chemin qui démarre réellement la balise : ce point n'est
    // atteint qu'APRÈS le gate consentement ci-dessous (granted d'entrée, ou
    // tq:consent-change → granted). Jamais avant, jamais si denied/absent.
    id = appareilId(opts.storage);
    if (!id) return; // Stockage indisponible : rien à corréler, on n'envoie rien.
    started = true;
    if (document.visibilityState === 'visible') acc.resume();
    demarrerBattement();
    window.addEventListener('pagehide', envoyerFinal);
    window.addEventListener('beforeunload', envoyerFinal);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        acc.pause();
        envoyer(false);
      } else if (document.visibilityState === 'visible') {
        acc.resume();
      }
    });
    window.addEventListener('pageshow', (e) => {
      if (!(e as PageTransitionEvent).persisted) return;
      // Restauration bfcache — le contexte JS survit tel quel (pas de rechargement) :
      // on réarme proprement plutôt que de laisser courir l'ancien état (l'intervalle
      // a déjà été annulé au pagehide, sentFinal déjà consommé). Le cumul repart de
      // ZÉRO, jamais depuis l'horodatage mural d'origine (F3#9).
      sentFinal = false;
      acc.reset();
      if (document.visibilityState === 'visible') acc.resume();
      demarrerBattement();
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
