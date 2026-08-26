// @vitest-environment jsdom
// ANALYT1 (audit item 64, 26/08/2026) — beacon de visibilité par section de
// la proposition. Deux volets, même découpage que visite.test.ts : le PUR
// (aucun DOM/réseau — construction du corps, nettoyage, accumulateur) et le
// COMPORTEMENTAL (`installerBaliseEngagement`, jsdom + IntersectionObserver
// injecté — jamais un vrai IntersectionObserver, jsdom ne l'implémente pas).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ENGAGEMENT_SECTION_ATTR,
  ENGAGEMENT_SECTION_KEYS,
  ENGAGEMENT_PROXY_PATH,
  ENGAGEMENT_FLUSH_DEBOUNCE_MS,
  buildEngagementBeaconBody,
  cleanEngagementSection,
  cleanEngagementSeconds,
  creerSuiviSection,
  creerVisitId,
  installerBaliseEngagement,
  isPlausibleVisitId,
  secondesEnAttente,
  type EngagementObserverEntry,
  type EngagementObserverFactory,
} from '../src/lib/engagementBeacon';

// ── Contrat de sections (miroir CÔTÉ TEST du DOM réel + du backend) ─────────

describe('ENGAGEMENT_SECTION_KEYS — contrat des sections suivies', () => {
  it('couvre exactement les 8 ancres réelles de la page proposition actuelle', () => {
    expect([...ENGAGEMENT_SECTION_KEYS].sort()).toEqual(
      ['calepinage', 'economies', 'graphs', 'hero', 'options', 'signature', 'sld', 'tailles'].sort(),
    );
  });
});

// ── Fonctions PURES ──────────────────────────────────────────────────────────

describe('cleanEngagementSection', () => {
  it('accepte une section whitelistée', () => {
    expect(cleanEngagementSection('tailles')).toBe('tailles');
    expect(cleanEngagementSection('signature')).toBe('signature');
  });

  it('rejette une section inconnue/arbitraire (jamais une section stockée hors whitelist)', () => {
    expect(cleanEngagementSection('bogus')).toBeNull();
    expect(cleanEngagementSection('')).toBeNull();
    expect(cleanEngagementSection(undefined)).toBeNull();
    expect(cleanEngagementSection(42)).toBeNull();
  });
});

describe('cleanEngagementSeconds', () => {
  it('arrondit et laisse passer une valeur positive raisonnable', () => {
    expect(cleanEngagementSeconds(12.6)).toBe(13);
    expect(cleanEngagementSeconds('7')).toBe(7);
  });

  it('renvoie 0 pour toute valeur non exploitable (négative, NaN, absente)', () => {
    expect(cleanEngagementSeconds(-5)).toBe(0);
    expect(cleanEngagementSeconds('abc')).toBe(0);
    expect(cleanEngagementSeconds(undefined)).toBe(0);
    expect(cleanEngagementSeconds(0)).toBe(0);
  });

  it('borne le garde-fou anti-garbage à 3600 s', () => {
    expect(cleanEngagementSeconds(999_999)).toBe(3600);
  });
});

describe('isPlausibleVisitId', () => {
  it('accepte un identifiant alphanumérique+tiret raisonnable', () => {
    expect(isPlausibleVisitId('a1b2c3-d4e5')).toBe(true);
  });

  it('rejette un identifiant vide, trop long, ou contenant un caractère hors whitelist', () => {
    expect(isPlausibleVisitId('')).toBe(false);
    expect(isPlausibleVisitId('x'.repeat(65))).toBe(false);
    expect(isPlausibleVisitId('a b')).toBe(false);
    expect(isPlausibleVisitId('a.b')).toBe(false);
    expect(isPlausibleVisitId(undefined)).toBe(false);
  });
});

describe('creerVisitId', () => {
  it('génère un identifiant plausible, différent à chaque appel', () => {
    const a = creerVisitId();
    const b = creerVisitId();
    expect(isPlausibleVisitId(a)).toBe(true);
    expect(isPlausibleVisitId(b)).toBe(true);
    expect(a).not.toBe(b);
  });
});

describe('buildEngagementBeaconBody', () => {
  const visitId = 'visit-abc123';

  it('construit le corps exact pour une section/seconds/visitId valides', () => {
    expect(buildEngagementBeaconBody('options', 12, visitId)).toEqual({
      section: 'options',
      seconds: 12,
      visit_id: visitId,
    });
  });

  it('renvoie null pour une section inconnue (rejet silencieux, jamais une erreur)', () => {
    expect(buildEngagementBeaconBody('bogus', 12, visitId)).toBeNull();
  });

  it('renvoie null pour 0 seconde (rien à envoyer)', () => {
    expect(buildEngagementBeaconBody('sld', 0, visitId)).toBeNull();
  });

  it('renvoie null pour un visitId malformé', () => {
    expect(buildEngagementBeaconBody('sld', 5, 'a b')).toBeNull();
    expect(buildEngagementBeaconBody('sld', 5, undefined)).toBeNull();
  });
});

describe('creerSuiviSection / secondesEnAttente', () => {
  it('accumule le temps VISIBLE et ne renvoie que le delta non-encore-transmis', () => {
    let t = 0;
    const now = () => t;
    const tracker = creerSuiviSection('economies', now);
    tracker.acc.resume();
    t += 5000; // 5 s visibles
    expect(secondesEnAttente(tracker)).toBe(5);

    tracker.sentSeconds += 5; // simule un flush déjà envoyé
    expect(secondesEnAttente(tracker)).toBe(0);

    t += 3000; // 3 s de plus
    expect(secondesEnAttente(tracker)).toBe(3);
  });

  it('ne compte pas le temps pendant une pause (section hors viewport)', () => {
    let t = 0;
    const now = () => t;
    const tracker = creerSuiviSection('graphs', now);
    tracker.acc.resume();
    t += 2000;
    tracker.acc.pause();
    t += 10_000; // hors viewport — ne doit rien ajouter
    expect(secondesEnAttente(tracker)).toBe(2);
  });
});

// ── Comportemental (jsdom + IntersectionObserver injecté) ──────────────────

/** Fabrique un IntersectionObserver FACTICE injectable — jsdom n'implémente
 *  pas IntersectionObserver nativement, et cette suite ne veut dépendre
 *  d'aucun polyfill : le callback capturé est déclenché à la main par
 *  chaque test (`trigger`), exactement comme le ferait un vrai observateur. */
function fakeObserverFactory() {
  let callback: ((entries: EngagementObserverEntry[]) => void) | null = null;
  const observed: Element[] = [];
  let disconnected = false;
  const factory: EngagementObserverFactory = (cb) => {
    callback = cb;
    return {
      observe(el: Element) {
        observed.push(el);
      },
      disconnect() {
        disconnected = true;
      },
    };
  };
  return {
    factory,
    observed,
    isDisconnected: () => disconnected,
    trigger(entries: EngagementObserverEntry[]) {
      callback?.(entries);
    },
  };
}

function buildRoot(sections: string[]): HTMLDivElement {
  const root = document.createElement('div');
  for (const key of sections) {
    const el = document.createElement('section');
    el.setAttribute(ENGAGEMENT_SECTION_ATTR, key);
    root.appendChild(el);
  }
  return root;
}

describe('installerBaliseEngagement', () => {
  let fetchFn: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    fetchFn = vi.fn().mockResolvedValue(new Response(null));
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    Object.defineProperty(navigator, 'sendBeacon', { value: undefined, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("n'installe RIEN quand apercuInterne est vrai (aperçu commercial interne)", () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['tailles']);
    const cleanup = installerBaliseEngagement('tok', {
      apercuInterne: true,
      root,
      fetchFn,
      observerFactory: obs.factory,
    });
    expect(cleanup).toBeUndefined();
    expect(obs.observed).toHaveLength(0);
  });

  it("n'installe RIEN quand la racine ne porte aucune section suivie", () => {
    const obs = fakeObserverFactory();
    const root = document.createElement('div');
    const cleanup = installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory });
    expect(cleanup).toBeUndefined();
    expect(obs.observed).toHaveLength(0);
  });

  it('observe chaque [data-track-section] de la racine', () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['hero', 'options', 'signature']);
    installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory });
    expect(obs.observed).toHaveLength(3);
  });

  it('envoie un beacon (fetch keepalive, sendBeacon absent) au flush débounce après une sortie de viewport', () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['options']);
    const el = root.firstElementChild as Element;
    installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory, visitId: 'visit-fixed-1' });

    obs.trigger([{ target: el, isIntersecting: true }]);
    vi.advanceTimersByTime(3000); // 3 s visibles
    obs.trigger([{ target: el, isIntersecting: false }]); // sortie de viewport → programme le flush

    expect(fetchFn).not.toHaveBeenCalled(); // pas encore — débounce en cours
    vi.advanceTimersByTime(ENGAGEMENT_FLUSH_DEBOUNCE_MS);

    expect(fetchFn).toHaveBeenCalledTimes(1);
    const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(ENGAGEMENT_PROXY_PATH);
    expect(init.keepalive).toBe(true);
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ token: 'tok', section: 'options', seconds: 3, visit_id: 'visit-fixed-1' });
  });

  it('utilise navigator.sendBeacon quand disponible plutôt que fetch', () => {
    const sendBeacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, 'sendBeacon', { value: sendBeacon, configurable: true });
    const obs = fakeObserverFactory();
    const root = buildRoot(['sld']);
    const el = root.firstElementChild as Element;
    installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory, visitId: 'v1' });

    obs.trigger([{ target: el, isIntersecting: true }]);
    vi.advanceTimersByTime(4000);
    obs.trigger([{ target: el, isIntersecting: false }]);
    vi.advanceTimersByTime(ENGAGEMENT_FLUSH_DEBOUNCE_MS);

    expect(sendBeacon).toHaveBeenCalledTimes(1);
    expect(fetchFn).not.toHaveBeenCalled();
    expect(sendBeacon.mock.calls[0]?.[0]).toBe(ENGAGEMENT_PROXY_PATH);
  });

  it('flush immédiatement au passage en visibilityState=hidden (jamais attendre le débounce)', () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['economies']);
    const el = root.firstElementChild as Element;
    installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory, visitId: 'v2' });

    obs.trigger([{ target: el, isIntersecting: true }]);
    vi.advanceTimersByTime(6000);
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));

    expect(fetchFn).toHaveBeenCalledTimes(1);
    const body = JSON.parse((fetchFn.mock.calls[0]?.[1] as RequestInit).body as string);
    expect(body.section).toBe('economies');
    expect(body.seconds).toBe(6);
  });

  it('flush au pagehide', () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['calepinage']);
    const el = root.firstElementChild as Element;
    installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory, visitId: 'v3' });

    obs.trigger([{ target: el, isIntersecting: true }]);
    vi.advanceTimersByTime(2000);
    window.dispatchEvent(new Event('pagehide'));

    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("n'envoie rien pour une section restée sous le seuil de 1 s (0 s accumulée)", () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['graphs']);
    const el = root.firstElementChild as Element;
    installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory, visitId: 'v4' });

    obs.trigger([{ target: el, isIntersecting: true }]);
    obs.trigger([{ target: el, isIntersecting: false }]); // sortie immédiate, 0 ms
    vi.advanceTimersByTime(ENGAGEMENT_FLUSH_DEBOUNCE_MS);

    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('le nettoyage (valeur de retour) déconnecte bien l’observateur', () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['hero']);
    const cleanup = installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory });
    expect(typeof cleanup).toBe('function');
    cleanup?.();
    expect(obs.isDisconnected()).toBe(true);
  });

  it('deux sections différentes partagent le MÊME visit_id sur une même page-load', () => {
    const obs = fakeObserverFactory();
    const root = buildRoot(['options', 'signature']);
    const [elA, elB] = Array.from(root.children);
    installerBaliseEngagement('tok', { root, fetchFn, observerFactory: obs.factory, visitId: 'shared-visit' });

    obs.trigger([{ target: elA, isIntersecting: true }]);
    vi.advanceTimersByTime(1000);
    obs.trigger([{ target: elA, isIntersecting: false }, { target: elB, isIntersecting: true }]);
    vi.advanceTimersByTime(1000);
    window.dispatchEvent(new Event('pagehide'));

    const bodies = fetchFn.mock.calls.map(([, init]) => JSON.parse((init as RequestInit).body as string));
    expect(bodies.every((b) => b.visit_id === 'shared-visit')).toBe(true);
  });
});
