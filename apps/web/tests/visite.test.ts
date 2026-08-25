// @vitest-environment jsdom
//
// LANE T-WEB (25/08/2026) — lib/visite.ts : balise de visite site entier
// (empreinte d'appareil + durée cumulée par page). Couvre le PUR (uuid
// stable, corps du beacon, validation) et le comportemental (demarrerBalise :
// no-op en aperçu interne, gate de consentement WB29/WB30/WB31, battement +
// envoi final au pagehide) — jsdom pour window/document/localStorage.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  appareilId,
  buildVisiteBeaconBody,
  cleanDureeS,
  cleanVisitePage,
  demarrerBalise,
  genererUuidV4,
  isPlausibleUuid,
  validateVisiteBody,
  VISITE_PROXY_PATH,
  type SimpleStorage,
} from '../src/lib/visite';

// ── genererUuidV4 / isPlausibleUuid ─────────────────────────────────────────

describe('genererUuidV4', () => {
  it('produit un UUID v4 bien formé (version 4, variant 8/9/a/b)', () => {
    for (let i = 0; i < 20; i++) {
      const id = genererUuidV4();
      expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    }
  });

  it('deux appels produisent des valeurs différentes (aléatoire réel)', () => {
    expect(genererUuidV4()).not.toBe(genererUuidV4());
  });

  it('repli manuel (randomFn injecté) reste conforme au format v4', () => {
    let seed = 0;
    const id = genererUuidV4(() => {
      seed = (seed + 0.1) % 1;
      return seed;
    });
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  });
});

describe('isPlausibleUuid', () => {
  it('accepte un UUID bien formé', () => {
    expect(isPlausibleUuid('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
  });
  it('refuse le garbage', () => {
    expect(isPlausibleUuid('pas-un-uuid')).toBe(false);
    expect(isPlausibleUuid('')).toBe(false);
    expect(isPlausibleUuid(undefined)).toBe(false);
    expect(isPlausibleUuid(42)).toBe(false);
  });
});

// ── appareilId (stockage injectable) ───────────────────────────────────────

function makeStorage(): SimpleStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k: string) => (data.has(k) ? data.get(k)! : null),
    setItem: (k: string, v: string) => {
      data.set(k, v);
    },
  };
}

describe('appareilId', () => {
  it('génère un uuid la première fois puis le RELIT (stable)', () => {
    const storage = makeStorage();
    const first = appareilId(storage);
    expect(isPlausibleUuid(first)).toBe(true);
    const second = appareilId(storage);
    expect(second).toBe(first);
    expect(storage.data.get('tq_appareil')).toBe(first);
  });

  it('une valeur existante malformée est remplacée par un uuid frais', () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', 'garbage-not-a-uuid');
    const id = appareilId(storage);
    expect(isPlausibleUuid(id)).toBe(true);
    expect(id).not.toBe('garbage-not-a-uuid');
  });

  it("'' quand le stockage est indisponible — jamais un throw", () => {
    // NOTE : un `undefined` explicite déclenche le paramètre par défaut
    // (`safeLocalStorage()`, qui réussit sous jsdom) — on force donc la
    // branche « pas de stockage du tout » avec un stockage nul explicite,
    // distinct du cas « le stockage lève », déjà couvert ci-dessous.
    expect(appareilId(null as unknown as SimpleStorage)).toBe('');
  });

  it('un stockage qui lève au setItem redescend une chaîne vide proprement (jamais bloquant)', () => {
    const storage: SimpleStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error('quota dépassé');
      },
    };
    expect(appareilId(storage)).toBe('');
  });
});

// ── cleanVisitePage / cleanDureeS ───────────────────────────────────────────

describe('cleanVisitePage', () => {
  it('conserve un chemin normal', () => {
    expect(cleanVisitePage('/devis/mon-toit')).toBe('/devis/mon-toit');
  });
  it('tronque la query string et le fragment', () => {
    expect(cleanVisitePage('/proposition/tok42?utm_source=fb#signer')).toBe('/proposition/tok42');
  });
  it("replie sur '/' si absent/malformé/hors-chemin", () => {
    expect(cleanVisitePage('')).toBe('/');
    expect(cleanVisitePage(undefined)).toBe('/');
    expect(cleanVisitePage('pas-un-chemin')).toBe('/');
    expect(cleanVisitePage('https://evil.example/x')).toBe('/');
  });
});

describe('cleanDureeS', () => {
  it('arrondit un nombre positif', () => {
    expect(cleanDureeS(12.6)).toBe(13);
  });
  it('0 pour négatif/NaN/absent', () => {
    expect(cleanDureeS(-5)).toBe(0);
    expect(cleanDureeS('pas-un-nombre')).toBe(0);
    expect(cleanDureeS(undefined)).toBe(0);
  });
  it('borné à 24h — jamais une durée absurde', () => {
    expect(cleanDureeS(999_999)).toBe(24 * 3600);
  });
});

// ── buildVisiteBeaconBody (corps du beacon) ─────────────────────────────────

describe('buildVisiteBeaconBody', () => {
  it('construit le contrat exact {appareil_id, page, duree_s, fin, langue}', () => {
    const body = buildVisiteBeaconBody('550e8400-e29b-41d4-a716-446655440000', '/index', 42.4, false, 'fr');
    expect(body).toEqual({
      appareil_id: '550e8400-e29b-41d4-a716-446655440000',
      page: '/index',
      duree_s: 42,
      fin: false,
      langue: 'fr',
    });
  });

  it('fin:true est préservé ; langue inconnue replie sur fr', () => {
    const body = buildVisiteBeaconBody('id', '/x', 0, true, 'de' as never);
    expect(body.fin).toBe(true);
    expect(body.langue).toBe('fr');
  });
});

describe('validateVisiteBody', () => {
  it('null quand appareil_id n’est pas un uuid plausible', () => {
    expect(validateVisiteBody({ appareil_id: 'nope', page: '/x', duree_s: 1, fin: false, langue: 'fr' })).toBeNull();
    expect(validateVisiteBody({})).toBeNull();
    expect(validateVisiteBody(null)).toBeNull();
  });

  it('nettoie et relaie un corps valide', () => {
    const result = validateVisiteBody({
      appareil_id: '550e8400-e29b-41d4-a716-446655440000',
      page: '/proposition/tok?x=1',
      duree_s: '19.9',
      fin: true,
      langue: 'ar',
    });
    expect(result).toEqual({
      appareil_id: '550e8400-e29b-41d4-a716-446655440000',
      page: '/proposition/tok',
      duree_s: 20,
      fin: true,
      langue: 'ar',
    });
  });
});

// ── demarrerBalise (comportemental, jsdom) ──────────────────────────────────

describe('demarrerBalise', () => {
  let storage: SimpleStorage & { data: Map<string, string> };
  let fetchFn: ReturnType<typeof vi.fn>;

  // `window`/`document` sont le SEUL jsdom global du fichier (pas un par test) :
  // demarrerBalise n'expose aucune poignée de nettoyage (comportement voulu —
  // une page réelle ne se « dé-démarre » jamais). On piste donc chaque
  // addEventListener posé pendant le test pour le retirer en afterEach, sinon
  // un pagehide/tq:consent-change dispatché par UN test réveille aussi les
  // écouteurs laissés par les tests précédents.
  let addedListeners: Array<[EventTarget, string, EventListenerOrEventListenerObject]>;

  beforeEach(() => {
    vi.useFakeTimers();
    storage = makeStorage();
    fetchFn = vi.fn().mockResolvedValue(new Response(null));
    // Consentement déjà accordé par défaut (le gate lui-même est testé à part).
    localStorage.setItem('tq_consent', 'granted');

    addedListeners = [];
    const origWindowAdd = window.addEventListener.bind(window);
    const origDocAdd = document.addEventListener.bind(document);
    vi.spyOn(window, 'addEventListener').mockImplementation((type, listener, opts) => {
      addedListeners.push([window, type, listener as EventListenerOrEventListenerObject]);
      origWindowAdd(type, listener as EventListener, opts);
    });
    vi.spyOn(document, 'addEventListener').mockImplementation((type, listener, opts) => {
      addedListeners.push([document, type, listener as EventListenerOrEventListenerObject]);
      origDocAdd(type, listener as EventListener, opts);
    });
  });

  afterEach(() => {
    for (const [target, type, listener] of addedListeners) {
      target.removeEventListener(type, listener as EventListener);
    }
    vi.useRealTimers();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("n'envoie RIEN quand apercuInterne est vrai (aperçu commercial interne)", () => {
    demarrerBalise('/proposition/tok', { apercuInterne: true, fetchFn, storage });
    vi.advanceTimersByTime(60_000);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("n'envoie RIEN tant que le consentement n'a jamais été accordé", () => {
    localStorage.removeItem('tq_consent');
    demarrerBalise('/index', { fetchFn, storage });
    vi.advanceTimersByTime(60_000);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("n'envoie RIEN quand le consentement est refusé", () => {
    localStorage.setItem('tq_consent', 'denied');
    demarrerBalise('/index', { fetchFn, storage });
    vi.advanceTimersByTime(60_000);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('démarre dès que le consentement devient accordé via tq:consent-change', () => {
    localStorage.removeItem('tq_consent');
    demarrerBalise('/index', { fetchFn, storage });
    expect(fetchFn).not.toHaveBeenCalled();
    window.dispatchEvent(new CustomEvent('tq:consent-change', { detail: { value: 'granted' } }));
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it('envoi immédiat (duree_s=0, fin=false) puis un battement toutes les ~20 s', () => {
    demarrerBalise('/index', { fetchFn, storage, intervalMs: 20_000 });
    expect(fetchFn).toHaveBeenCalledTimes(1);
    const firstBody = JSON.parse((fetchFn.mock.calls[0]?.[1] as RequestInit).body as string);
    expect(firstBody.duree_s).toBe(0);
    expect(firstBody.fin).toBe(false);
    expect(firstBody.page).toBe('/index');
    expect(isPlausibleUuid(firstBody.appareil_id)).toBe(true);

    vi.advanceTimersByTime(20_000);
    expect(fetchFn).toHaveBeenCalledTimes(2);
    const secondBody = JSON.parse((fetchFn.mock.calls[1]?.[1] as RequestInit).body as string);
    expect(secondBody.duree_s).toBeGreaterThanOrEqual(19);
  });

  it('poste vers VISITE_PROXY_PATH', () => {
    demarrerBalise('/index', { fetchFn, storage });
    expect(fetchFn.mock.calls[0]?.[0]).toBe(VISITE_PROXY_PATH);
  });

  it('envoie fin:true via navigator.sendBeacon au pagehide', () => {
    const sendBeacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, 'sendBeacon', { value: sendBeacon, configurable: true });
    demarrerBalise('/index', { fetchFn, storage });
    window.dispatchEvent(new Event('pagehide'));
    expect(sendBeacon).toHaveBeenCalledTimes(1);
    expect(sendBeacon.mock.calls[0]?.[0]).toBe(VISITE_PROXY_PATH);
  });

  it("n'envoie rien si l'empreinte d'appareil est indisponible (stockage nul)", () => {
    // Même nuance que ci-dessus : `storage: undefined` retomberait sur le
    // localStorage réel de jsdom (id généré avec succès) — `null` force la
    // branche « rien à corréler » sans dépendre de l'environnement de test.
    demarrerBalise('/index', { fetchFn, storage: null as unknown as SimpleStorage });
    vi.advanceTimersByTime(60_000);
    expect(fetchFn).not.toHaveBeenCalled();
  });
});
