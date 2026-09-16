// @vitest-environment jsdom
//
// LANE T-WEB — QJ-EQUIPE cookie partagé ERP↔site (T1, correctif « notification
// lecture devis » 16/09/2026). Couvre le PUR (`domaineCookiePartage`,
// `lireCookie`, `serialiserCookie`) et le comportemental (`appareilId` avec un
// `SimpleCookieStore` injecté — priorité cookie/storage, miroir dans les deux
// sens, génération, storage indisponible, attributs du cookie posé). Même
// style que `tests/lead.test.ts`/`tests/visite.test.ts` — jsdom pour
// window/document, mais un cookie store INJECTÉ (jamais le vrai
// `document.cookie`) pour rester isolé des autres fichiers de test.
//
// M2 (passe adversariale, correctif) — `demarrerBalise` ne calcule
// `appareilId()` (cookie 2 ans + localStorage, T1) que DANS `demarrer()`,
// donc jamais avant le gate consentement `tq_consent` : le dernier describe
// ci-dessous vérifie ce point précis sur le vrai `document.cookie` (jsdom,
// espionné via le descripteur d'accesseur) — `demarrerBalise` n'expose pas
// de cookie store injectable (seul `storage` l'est), donc on espionne la
// vraie écriture plutôt que d'en injecter une fausse.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  appareilId,
  demarrerBalise,
  domaineCookiePartage,
  isPlausibleUuid,
  lireCookie,
  serialiserCookie,
  SITE_HOST,
  type SimpleCookieSetAttrs,
  type SimpleCookieStore,
  type SimpleStorage,
} from '../src/lib/visite';

// ── SITE_HOST ────────────────────────────────────────────────────────────────

describe('SITE_HOST', () => {
  it('est le domaine canonique du site (miroir de astro.config.mjs)', () => {
    expect(SITE_HOST).toBe('taqinor.ma');
  });
});

// ── domaineCookiePartage ─────────────────────────────────────────────────────

describe('domaineCookiePartage', () => {
  it('renvoie SITE_HOST pour le site lui-même', () => {
    expect(domaineCookiePartage('taqinor.ma', 'taqinor.ma')).toBe('taqinor.ma');
  });

  it('renvoie SITE_HOST pour un sous-domaine (www, api…)', () => {
    expect(domaineCookiePartage('www.taqinor.ma', 'taqinor.ma')).toBe('taqinor.ma');
    expect(domaineCookiePartage('api.taqinor.ma', 'taqinor.ma')).toBe('taqinor.ma');
  });

  it('undefined pour localhost — jamais un cookie Domain refusé par le navigateur', () => {
    expect(domaineCookiePartage('localhost', 'taqinor.ma')).toBeUndefined();
  });

  it("undefined pour un aperçu *.workers.dev — 'taqinor' au début du host n'est PAS un sous-domaine", () => {
    expect(domaineCookiePartage('taqinor-web.taqinor.workers.dev', 'taqinor.ma')).toBeUndefined();
  });

  it('undefined pour un hôte totalement étranger', () => {
    expect(domaineCookiePartage('evil.example', 'taqinor.ma')).toBeUndefined();
  });

  it('undefined si hostname ou siteHost est vide — jamais un throw', () => {
    expect(domaineCookiePartage('', 'taqinor.ma')).toBeUndefined();
    expect(domaineCookiePartage('taqinor.ma', '')).toBeUndefined();
  });

  it('utilise SITE_HOST par défaut quand siteHost est omis', () => {
    expect(domaineCookiePartage('taqinor.ma')).toBe('taqinor.ma');
    expect(domaineCookiePartage('localhost')).toBeUndefined();
  });
});

// ── lireCookie ───────────────────────────────────────────────────────────────

describe('lireCookie', () => {
  it('extrait une valeur parmi plusieurs cookies (format document.cookie / en-tête Cookie)', () => {
    expect(lireCookie('tq_consent=granted; tq_appareil=abc-123; tq_equipe=1', 'tq_appareil')).toBe('abc-123');
    expect(lireCookie('tq_consent=granted; tq_appareil=abc-123; tq_equipe=1', 'tq_equipe')).toBe('1');
  });

  it('undefined quand le cookie est absent', () => {
    expect(lireCookie('tq_consent=granted', 'tq_appareil')).toBeUndefined();
  });

  it('undefined quand l’en-tête est vide/absent — jamais un throw', () => {
    expect(lireCookie('', 'tq_appareil')).toBeUndefined();
    expect(lireCookie(null, 'tq_appareil')).toBeUndefined();
    expect(lireCookie(undefined, 'tq_appareil')).toBeUndefined();
  });

  it('décode une valeur percent-encodée', () => {
    expect(lireCookie('tq_appareil=a%2Fb%3Dc', 'tq_appareil')).toBe('a/b=c');
  });

  it('tolère les espaces autour des « ; » (format document.cookie réel)', () => {
    expect(lireCookie('a=1;   tq_appareil=xyz  ;b=2', 'tq_appareil')).toBe('xyz');
  });
});

// ── serialiserCookie ─────────────────────────────────────────────────────────

describe('serialiserCookie — attributs du cookie posé', () => {
  const base: SimpleCookieSetAttrs = {
    path: '/',
    maxAgeSeconds: 63072000,
    sameSite: 'Lax',
    secure: true,
    domain: undefined,
  };

  it('porte Path, Max-Age, SameSite=Lax, Secure', () => {
    const out = serialiserCookie('tq_appareil', 'abc-123', base);
    expect(out).toContain('tq_appareil=abc-123');
    expect(out).toContain('Path=/');
    expect(out).toContain('Max-Age=63072000');
    expect(out).toContain('SameSite=Lax');
    expect(out).toContain('Secure');
  });

  it('Domain ABSENT quand attrs.domain est undefined (cookie host-only)', () => {
    const out = serialiserCookie('tq_appareil', 'abc-123', base);
    expect(out).not.toContain('Domain=');
  });

  it('Domain PRÉSENT quand attrs.domain est fourni', () => {
    const out = serialiserCookie('tq_appareil', 'abc-123', { ...base, domain: 'taqinor.ma' });
    expect(out).toContain('Domain=taqinor.ma');
  });

  it('Secure ABSENT quand attrs.secure est faux', () => {
    const out = serialiserCookie('tq_appareil', 'abc-123', { ...base, secure: false });
    expect(out).not.toContain('Secure');
  });

  it('encode la valeur', () => {
    const out = serialiserCookie('tq_appareil', 'a/b=c', base);
    expect(out).toContain('tq_appareil=a%2Fb%3Dc');
  });
});

// ── appareilId — cookie store injecté (jamais le vrai document.cookie) ───────

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

function makeCookieStore(): SimpleCookieStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    get: vi.fn((name: string) => data.get(name)),
    set: vi.fn((name: string, value: string) => {
      data.set(name, value);
    }),
  };
}

const UUID_A = '550e8400-e29b-41d4-a716-446655440000';
const UUID_B = '6ba7b810-9dad-11d1-80b4-00c04fd430c8';

describe('appareilId — priorité cookie > storage', () => {
  it('le cookie plausible gagne même si le storage porte déjà une AUTRE valeur plausible', () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', UUID_B);
    const cookies = makeCookieStore();
    cookies.data.set('tq_appareil', UUID_A);

    const id = appareilId(storage, cookies);
    expect(id).toBe(UUID_A);
  });

  it('miroir cookie→storage : le storage est réécrit avec la valeur du cookie', () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', UUID_B);
    const cookies = makeCookieStore();
    cookies.data.set('tq_appareil', UUID_A);

    appareilId(storage, cookies);
    expect(storage.data.get('tq_appareil')).toBe(UUID_A);
  });

  it('un cookie garbage est ignoré — le storage plausible reprend la main', () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', UUID_A);
    const cookies = makeCookieStore();
    cookies.data.set('tq_appareil', 'pas-un-uuid');

    expect(appareilId(storage, cookies)).toBe(UUID_A);
  });

  it('aucune écriture storage si le cookie est déjà identique à la valeur existante', () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', UUID_A);
    const cookies = makeCookieStore();
    cookies.data.set('tq_appareil', UUID_A);
    const setItemSpy = vi.spyOn(storage, 'setItem');

    expect(appareilId(storage, cookies)).toBe(UUID_A);
    expect(setItemSpy).not.toHaveBeenCalled();
  });
});

describe('appareilId — miroir storage→cookie', () => {
  it("le storage plausible (cookie absent) est renvoyé ET posé en cookie", () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', UUID_A);
    const cookies = makeCookieStore();

    const id = appareilId(storage, cookies);
    expect(id).toBe(UUID_A);
    expect(cookies.set).toHaveBeenCalledTimes(1);
    expect(cookies.set).toHaveBeenCalledWith('tq_appareil', UUID_A, expect.objectContaining({
      path: '/',
      maxAgeSeconds: 63072000,
      sameSite: 'Lax',
      secure: true,
    }));
  });

  it('le domaine de l’attribut posé correspond exactement à domaineCookiePartage(hostname courant)', () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', UUID_A);
    const cookies = makeCookieStore();

    appareilId(storage, cookies);
    const attrs = (cookies.set as ReturnType<typeof vi.fn>).mock.calls[0]?.[2] as SimpleCookieSetAttrs;
    expect(attrs.domain).toBe(domaineCookiePartage(window.location.hostname));
  });
});

describe('appareilId — génération → pose les deux', () => {
  it("ni cookie ni storage : génère un uuid frais, le pose en storage ET en cookie", () => {
    const storage = makeStorage();
    const cookies = makeCookieStore();

    const id = appareilId(storage, cookies);
    expect(isPlausibleUuid(id)).toBe(true);
    expect(storage.data.get('tq_appareil')).toBe(id);
    expect(cookies.data.get('tq_appareil')).toBe(id);
    expect(cookies.set).toHaveBeenCalledWith('tq_appareil', id, expect.any(Object));
  });

  it('une valeur storage malformée (ni cookie ni storage plausibles) est remplacée par un uuid frais', () => {
    const storage = makeStorage();
    storage.setItem('tq_appareil', 'garbage-not-a-uuid');
    const cookies = makeCookieStore();
    cookies.data.set('tq_appareil', 'aussi-du-garbage');

    const id = appareilId(storage, cookies);
    expect(isPlausibleUuid(id)).toBe(true);
    expect(id).not.toBe('garbage-not-a-uuid');
  });
});

describe('appareilId — stockage indisponible', () => {
  it("'' quand storage est indisponible — jamais de lecture/écriture cookie (court-circuit)", () => {
    const cookies = makeCookieStore();
    cookies.data.set('tq_appareil', UUID_A); // même un cookie plausible présent ne sauve pas l'appel.

    expect(appareilId(null as unknown as SimpleStorage, cookies)).toBe('');
    expect(cookies.get).not.toHaveBeenCalled();
    expect(cookies.set).not.toHaveBeenCalled();
  });

  it("'' quand le storage lève à l'écriture — même si le cookie a pu être posé (storage cassé = rien de fiable)", () => {
    const storage: SimpleStorage = {
      getItem: () => null,
      setItem: () => {
        throw new Error('quota dépassé');
      },
    };
    const cookies = makeCookieStore();

    expect(appareilId(storage, cookies)).toBe('');
  });

  it("un cookies store qui lève est traité comme absent — jamais bloquant", () => {
    const storage = makeStorage();
    const throwingCookies: SimpleCookieStore = {
      get: () => {
        throw new Error('cookie API indisponible');
      },
      set: () => {
        throw new Error('cookie API indisponible');
      },
    };

    const id = appareilId(storage, throwingCookies);
    expect(isPlausibleUuid(id)).toBe(true);
    expect(storage.data.get('tq_appareil')).toBe(id);
  });
});

// ── demarrerBalise — le cookie/localStorage tq_appareil ne s'écrivent qu'APRÈS
// consentement (M2) ─────────────────────────────────────────────────────────
//
// `demarrerBalise` n'expose pas de `cookies` injectable (seul `storage` l'est,
// voir `DemarrerBaliseOptions`) : pour vérifier qu'AUCUNE écriture cookie ne
// part avant consentement, on espionne le vrai accesseur `document.cookie`
// (jsdom) — ce qui détecte une TENTATIVE d'écriture même si jsdom refusait par
// ailleurs de persister un cookie Secure sous une origine http:// de test.

describe("demarrerBalise — consentement gate le cookie ET le localStorage (M2)", () => {
  let addedListeners: Array<[EventTarget, string, EventListenerOrEventListenerObject]>;
  let cookieWrites: string[];
  let originalCookieDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    vi.useFakeTimers();
    // Jamais de résidu d'un test précédent du fichier (document partagé par jsdom).
    document.cookie = 'tq_appareil=; Max-Age=0; path=/';
    localStorage.removeItem('tq_appareil');
    localStorage.removeItem('tq_consent');

    cookieWrites = [];
    originalCookieDescriptor =
      Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') ??
      Object.getOwnPropertyDescriptor(document, 'cookie');
    if (!originalCookieDescriptor?.get || !originalCookieDescriptor.set) {
      throw new Error("document.cookie n'expose pas d'accesseur get/set — jsdom inattendu, à investiguer.");
    }
    const { get, set } = originalCookieDescriptor;
    Object.defineProperty(document, 'cookie', {
      configurable: true,
      get() {
        return get.call(document);
      },
      set(value: string) {
        cookieWrites.push(value);
        set.call(document, value);
      },
    });

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
    document.cookie = 'tq_appareil=; Max-Age=0; path=/';
    if (originalCookieDescriptor) {
      Object.defineProperty(document, 'cookie', originalCookieDescriptor);
    }
    vi.useRealTimers();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  // Réutilise le `makeStorage()` module-level déjà défini plus haut (même
  // fixture qu'`appareilId` — pas de doublon).

  it("consentement ABSENT : aucune écriture cookie ni localStorage tq_appareil", () => {
    const storage = makeStorage();
    const setItemSpy = vi.spyOn(storage, 'setItem');
    demarrerBalise('/index', { storage, fetchFn: vi.fn().mockResolvedValue(new Response(null)) });
    vi.advanceTimersByTime(60_000);

    expect(setItemSpy).not.toHaveBeenCalled();
    expect(cookieWrites.some((w) => w.startsWith('tq_appareil='))).toBe(false);
  });

  it("consentement DENIED : aucune écriture cookie ni localStorage tq_appareil", () => {
    localStorage.setItem('tq_consent', 'denied');
    const storage = makeStorage();
    const setItemSpy = vi.spyOn(storage, 'setItem');
    demarrerBalise('/index', { storage, fetchFn: vi.fn().mockResolvedValue(new Response(null)) });
    vi.advanceTimersByTime(60_000);

    expect(setItemSpy).not.toHaveBeenCalled();
    expect(cookieWrites.some((w) => w.startsWith('tq_appareil='))).toBe(false);
  });

  it("consentement GRANTED d'entrée : écrit le localStorage ET tente l'écriture du cookie", () => {
    localStorage.setItem('tq_consent', 'granted');
    const storage = makeStorage();
    demarrerBalise('/index', { storage, fetchFn: vi.fn().mockResolvedValue(new Response(null)) });

    expect(storage.data.has('tq_appareil')).toBe(true);
    expect(cookieWrites.some((w) => w.startsWith('tq_appareil='))).toBe(true);
  });

  it("consentement accordé APRÈS coup (tq:consent-change) : rien avant, tout après", () => {
    const storage = makeStorage();
    const setItemSpy = vi.spyOn(storage, 'setItem');
    demarrerBalise('/index', { storage, fetchFn: vi.fn().mockResolvedValue(new Response(null)) });
    vi.advanceTimersByTime(30_000);
    expect(setItemSpy).not.toHaveBeenCalled();
    expect(cookieWrites.some((w) => w.startsWith('tq_appareil='))).toBe(false);

    window.dispatchEvent(new CustomEvent('tq:consent-change', { detail: { value: 'granted' } }));

    expect(setItemSpy).toHaveBeenCalled();
    expect(cookieWrites.some((w) => w.startsWith('tq_appareil='))).toBe(true);
  });
});
