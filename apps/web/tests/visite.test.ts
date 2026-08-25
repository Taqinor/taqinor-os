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
  creerAccumulateurTempsVisible,
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

  // F3#7 — le jeton porteur (43+ caractères) ne doit JAMAIS fuiter en entier
  // dans `page` (persisté en base, réémis dans les alertes commerciaux).
  const TOKEN_43 = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d';

  it('masque le jeton de /proposition/<token> (sans slug)', () => {
    expect(cleanVisitePage(`/proposition/${TOKEN_43}`)).toBe(`/proposition/…${TOKEN_43.slice(-6)}`);
  });

  it('masque le jeton de /proposition/<slug>/<token> tout en gardant le slug décoratif', () => {
    expect(cleanVisitePage(`/proposition/villa-oceane/${TOKEN_43}`)).toBe(
      `/proposition/villa-oceane/…${TOKEN_43.slice(-6)}`,
    );
  });

  it('masque le jeton de /questionnaire/<token>', () => {
    expect(cleanVisitePage(`/questionnaire/${TOKEN_43}`)).toBe(`/questionnaire/…${TOKEN_43.slice(-6)}`);
  });

  it('ne masque PAS un segment court (≤ 24 caractères, ex. un slug ou "tok42" de test)', () => {
    expect(cleanVisitePage('/proposition/villa-oceane')).toBe('/proposition/villa-oceane');
    expect(cleanVisitePage('/proposition/tok42')).toBe('/proposition/tok42');
  });

  it('la query/fragment tronquée AVANT masquage ne laisse pas fuiter un jeton placé après "?"', () => {
    expect(cleanVisitePage(`/proposition/${TOKEN_43}?ref=${TOKEN_43}`)).toBe(`/proposition/…${TOKEN_43.slice(-6)}`);
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

// ── creerAccumulateurTempsVisible (F3#9, pur, horloge injectable) ──────────

describe('creerAccumulateurTempsVisible', () => {
  it('cumule seulement le temps entre resume() et pause() — jamais le temps mural en dehors', () => {
    let t = 0;
    const acc = creerAccumulateurTempsVisible(() => t);
    acc.resume();
    t = 5000;
    acc.pause();
    t = 999_000; // le "mur" avance loin pendant que la page est masquée…
    expect(acc.totalMs()).toBe(5000); // … mais le cumul n'a pas bougé.
  });

  it('totalMs() inclut le segment visible EN COURS sans pause()', () => {
    let t = 0;
    const acc = creerAccumulateurTempsVisible(() => t);
    acc.resume();
    t = 3000;
    expect(acc.totalMs()).toBe(3000);
  });

  it('resume()/pause() répétés accumulent plusieurs segments visibles', () => {
    let t = 0;
    const acc = creerAccumulateurTempsVisible(() => t);
    acc.resume();
    t = 2000;
    acc.pause();
    t = 500_000; // masqué longtemps…
    acc.resume(); // … puis re-visible.
    t = 502_000;
    acc.pause();
    expect(acc.totalMs()).toBe(4000); // 2000 + (502000-500000) = 4000, jamais 502000.
  });

  it('reset() repart de zéro — jamais une reprise depuis le mur', () => {
    let t = 0;
    const acc = creerAccumulateurTempsVisible(() => t);
    acc.resume();
    t = 10_000;
    acc.reset();
    expect(acc.totalMs()).toBe(0);
    t = 10_500;
    acc.resume();
    t = 11_000;
    expect(acc.totalMs()).toBe(500);
  });

  it('pause() sans resume() préalable est un no-op sûr', () => {
    const acc = creerAccumulateurTempsVisible(() => 1000);
    acc.pause();
    expect(acc.totalMs()).toBe(0);
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
    // F3#9 — `visibilityState` n'est pas remis par vi.restoreAllMocks() (c'est
    // un Object.defineProperty direct, pas un spy) : on le réarme à 'visible'
    // ici pour que chaque test reparte d'un état connu, quel que soit ce
    // qu'un test précédent a laissé.
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    // Même nuance pour `navigator.sendBeacon` : un test plus haut le définit
    // via Object.defineProperty (jamais restauré par vi.restoreAllMocks(),
    // qui ne suit que les spies) — sans ce réarmement, ce mock fuitait vers
    // TOUS les tests suivants du fichier (fin:true partait alors par
    // sendBeacon au lieu de fetchFn, invisible à l'inspection du corps JSON).
    Object.defineProperty(navigator, 'sendBeacon', { value: undefined, configurable: true });

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

  // F3#9 — cumul SOUS VISIBILITÉ : le temps mural passé onglet masqué ne doit
  // JAMAIS inventer une durée. `intervalMs` volontairement énorme dans ces
  // deux tests pour isoler la variable testée (pas de battement parasite).
  it("le temps masqué (onglet caché) n'est PAS compté dans duree_s — jamais un temps mural", () => {
    demarrerBalise('/index', { fetchFn, storage, intervalMs: 999_999_999 });
    vi.advanceTimersByTime(5000); // 5 s visibles

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    const hiddenBody = JSON.parse(
      (fetchFn.mock.calls[fetchFn.mock.calls.length - 1]?.[1] as RequestInit).body as string,
    );
    expect(hiddenBody.duree_s).toBeGreaterThanOrEqual(4);
    expect(hiddenBody.duree_s).toBeLessThanOrEqual(6);

    vi.advanceTimersByTime(3 * 3600 * 1000); // le mur avance 3 h pendant que c'est masqué

    window.dispatchEvent(new Event('pagehide'));
    const finalBody = JSON.parse(
      (fetchFn.mock.calls[fetchFn.mock.calls.length - 1]?.[1] as RequestInit).body as string,
    );
    expect(finalBody.fin).toBe(true);
    expect(finalBody.duree_s).toBeLessThan(10); // jamais ~10800 (3 h de mur)
  });

  it('pageshow(persisted) après un pagehide réarme le cumul à zéro + sentFinal — jamais une reprise du mur (bfcache)', () => {
    demarrerBalise('/index', { fetchFn, storage, intervalMs: 999_999_999 });
    vi.advanceTimersByTime(2000);

    window.dispatchEvent(new Event('pagehide')); // envoi final, annule le battement
    const callsAfterFirstPagehide = fetchFn.mock.calls.length;

    vi.advanceTimersByTime(3 * 3600 * 1000); // le mur avance 3 h pendant le bfcache

    const pageshow = new Event('pageshow');
    Object.defineProperty(pageshow, 'persisted', { value: true });
    window.dispatchEvent(pageshow);

    // Le réarmement relance un battement immédiat frais (duree_s ≈ 0, pas ~3 h).
    expect(fetchFn.mock.calls.length).toBe(callsAfterFirstPagehide + 1);
    const restoredBody = JSON.parse(
      (fetchFn.mock.calls[fetchFn.mock.calls.length - 1]?.[1] as RequestInit).body as string,
    );
    expect(restoredBody.duree_s).toBeLessThan(2);
    expect(restoredBody.fin).toBe(false);

    // sentFinal a bien été réarmé : un second pagehide peut renvoyer fin:true.
    vi.advanceTimersByTime(1000);
    window.dispatchEvent(new Event('pagehide'));
    const secondFinal = JSON.parse(
      (fetchFn.mock.calls[fetchFn.mock.calls.length - 1]?.[1] as RequestInit).body as string,
    );
    expect(secondFinal.fin).toBe(true);
    expect(secondFinal.duree_s).toBeLessThan(3);
  });

  it("un pageshow SANS persisted (navigation normale, pas de bfcache) ne réarme rien", () => {
    demarrerBalise('/index', { fetchFn, storage, intervalMs: 999_999_999 });
    vi.advanceTimersByTime(2000);
    const callsBefore = fetchFn.mock.calls.length;

    window.dispatchEvent(new Event('pageshow')); // persisted est false par défaut
    expect(fetchFn.mock.calls.length).toBe(callsBefore); // aucun envoi supplémentaire
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
