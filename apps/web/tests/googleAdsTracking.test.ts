// @vitest-environment jsdom
/**
 * Google Ads / Google tag — suivi des leads du site.
 *  - lib/googleTag.ts : lecture des 2 variables d'env (aucun ID ⇒ rien) ;
 *  - GoogleTag.astro : ne rend RIEN sans ID, gate consentement comme MetaPixel ;
 *  - lib/lead.ts : gclid/gbraid/wbraid transmis au CRM (whitelist), absents sinon ;
 *  - tunnel : tqGoogleTrack appelé au même endroit et avec le même eventId que
 *    tqPixelTrack('Lead') ; capture first-touch identique à fbclid ;
 *  - CSP : hôtes Google présents.
 */
import { readFileSync } from 'node:fs';
import { lireSourceTunnel } from './astroBlocsHelper';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { parseGoogleTagIds, parseLeadSendTo } from '../src/lib/googleTag';
import { buildLeadRecord, forwardLead, runSimulation, validateLead } from '../src/lib/lead';
import { etatVide } from '../src/lib/tunnel/champs';
import { construireCorps } from '../src/lib/tunnel/corps';
import { CONTENT_SECURITY_POLICY } from '../worker/headers.mjs';

const read = (rel: string) => lireSourceTunnel(fileURLToPath(new URL(rel, import.meta.url)));

const body = {
  fullName: 'Karim Benali',
  phone: '06 12 34 56 78',
  whatsappOptIn: true,
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

describe('lib/googleTag — variables d’environnement', () => {
  it('aucun ID ⇒ liste vide (le composant ne rendra rien)', () => {
    expect(parseGoogleTagIds(undefined)).toEqual([]);
    expect(parseGoogleTagIds('')).toEqual([]);
    expect(parseGoogleTagIds('  ,  ')).toEqual([]);
  });

  it('plusieurs ID séparés par des virgules, dédoublonnés, malformés écartés', () => {
    expect(parseGoogleTagIds(' AW-123456789 , G-ABC123XYZ,AW-123456789')).toEqual(['AW-123456789', 'G-ABC123XYZ']);
    expect(parseGoogleTagIds("AW-1<script>,G-OK1")).toEqual(['G-OK1']);
  });

  it('send_to de conversion : AW-XXX/libellé seulement', () => {
    expect(parseLeadSendTo('AW-123456789/AbC-d_9')).toBe('AW-123456789/AbC-d_9');
    expect(parseLeadSendTo('G-ABC/x')).toBe('');
    expect(parseLeadSendTo(undefined)).toBe('');
  });
});

describe('GoogleTag.astro', () => {
  const src = read('../src/components/GoogleTag.astro');

  it('ne rend rien sans ID (markup entièrement gaté sur tagIds.length)', () => {
    expect(src).toContain('parseGoogleTagIds(import.meta.env.PUBLIC_GOOGLE_TAG_ID');
    const markup = src.split(/^---$/m)[2] ?? '';
    expect(markup.trim().startsWith('{tagIds.length > 0 && (')).toBe(true);
  });

  it('tqGoogleTrack : conversion Ads (si send_to) + generate_lead, transaction_id = eventId', () => {
    expect(src).toContain('window.tqGoogleTrack = function (eventId)');
    expect(src).toContain("window.gtag('event', 'conversion'");
    expect(src).toContain("window.gtag('event', 'generate_lead'");
    expect(src).toContain('transaction_id: String(eventId)');
  });

  it('inclus dans le Layout avec la même exclusion noindex que MetaPixel', () => {
    const layout = read('../src/layouts/Layout.astro');
    expect(layout).toContain('{mesure && <MetaPixel />}');
    expect(layout).toContain('{mesure && <GoogleTag />}');
  });
});

describe('capture et transmission des identifiants de clic Google', () => {
  it('le Layout capture gclid/gbraid/wbraid avec fbclid (même first-touch)', () => {
    const layout = read('../src/layouts/Layout.astro');
    expect(layout).toContain("var keys = ['fbclid', 'gclid', 'gbraid', 'wbraid', 'utm_source'");
  });

  it('validateLead joint gclid/gbraid/wbraid présents, rien quand absents', () => {
    const avec = validateLead({ ...body, gclid: ' Cj0KCQ-g ', gbraid: 'gb1', wbraid: 'wb1', evil: 'x' });
    expect(avec.ok).toBe(true);
    if (!avec.ok) return;
    expect(avec.lead.gclid).toBe('Cj0KCQ-g');
    expect(avec.lead.gbraid).toBe('gb1');
    expect(avec.lead.wbraid).toBe('wb1');
    expect(avec.lead).not.toHaveProperty('evil');
    const sans = validateLead(body);
    expect(sans.ok).toBe(true);
    if (!sans.ok) return;
    for (const k of ['gclid', 'gbraid', 'wbraid']) expect(sans.lead).not.toHaveProperty(k);
  });

  it('gclid tronqué à 255', () => {
    const r = validateLead({ ...body, gclid: 'x'.repeat(400) });
    expect(r.ok && r.lead.gclid?.length).toBe(255);
  });

  it('forwardLead envoie gclid au webhook CRM', async () => {
    let sent = '';
    const fetchFn = vi.fn(async (_u: unknown, init?: RequestInit) => {
      sent = String(init?.body);
      return new Response('ok');
    }) as unknown as typeof fetch;
    const v = validateLead({ ...body, gclid: 'Cj0KCQ-g' });
    if (!v.ok) throw new Error('fixture invalide');
    const band = await runSimulation(v.lead, {});
    const record = buildLeadRecord(v.lead, band, new Date('2026-10-06T10:00:00Z'));
    await forwardLead(record, { LEAD_WEBHOOK_URL: 'https://crm.example/hook' }, fetchFn);
    expect(JSON.parse(sent).gclid).toBe('Cj0KCQ-g');
  });

  it('le registre du tunnel joint gclid/gbraid/wbraid présents seulement', () => {
    const corps = (tracking: Record<string, string>) =>
      construireCorps({ ...etatVide(), tracking }, { messages: { nomComplet: 'Nom complet requis' } }).body;
    const avec = corps({ gclid: 'g1', gbraid: 'b1', wbraid: 'w1' });
    expect(avec.gclid).toBe('g1');
    expect(avec.gbraid).toBe('b1');
    expect(avec.wbraid).toBe('w1');
    const sans = corps({});
    for (const k of ['gclid', 'gbraid', 'wbraid']) expect(sans).not.toHaveProperty(k);
  });
});

describe('tunnel FR/EN/AR — tqGoogleTrack partout où part tqPixelTrack(Lead)', () => {
  it.each([
    ['FR', '../src/pages/devis/mon-toit.astro'],
    ['EN', '../src/pages/en/devis/mon-toit.astro'],
    ['AR', '../src/pages/ar/devis/mon-toit.astro'],
  ])('%s', (_l, rel) => {
    const src = read(rel);
    const pixel = src.indexOf(".tqPixelTrack?.('Lead', {}, getOrCreateDedupTokens().eventId);");
    const google = src.indexOf('.tqGoogleTrack?.(getOrCreateDedupTokens().eventId);');
    expect(pixel).toBeGreaterThan(0);
    expect(google).toBeGreaterThan(pixel);
    // Même bloc (lead qualifié) : rien d'autre qu'un commentaire entre les deux.
    expect(google - pixel).toBeLessThan(400);
    expect(src).toContain("const TRACK_KEYS = ['fbclid', 'gclid', 'gbraid', 'wbraid',");
  });
});

describe('CSP — hôtes Google tag', () => {
  const directive = (name: string) =>
    CONTENT_SECURITY_POLICY.split(';').map((d) => d.trim()).find((d) => d.startsWith(name + ' ')) ?? '';

  it('script-src autorise gtag.js', () => {
    expect(directive('script-src')).toContain('https://www.googletagmanager.com');
  });

  it('connect-src / img-src autorisent les pings Analytics et Ads', () => {
    for (const host of ['https://www.google-analytics.com', 'https://*.google-analytics.com', 'https://www.google.com', 'https://*.g.doubleclick.net']) {
      expect(directive('connect-src'), host).toContain(host);
    }
    for (const host of ['https://*.google-analytics.com', 'https://www.google.com', 'https://*.g.doubleclick.net']) {
      expect(directive('img-src'), host).toContain(host);
    }
  });

  it("frame-src garde 'self' (ancien repli default-src) + googletagmanager", () => {
    expect(directive('frame-src')).toBe("frame-src 'self' https://www.googletagmanager.com https://www.facebook.com");
  });
});

// WAUD12 — on exécute les VRAIS scripts des composants : ils ne doivent rien
// charger ni rien envoyer avant « Accepter », et jamais perdre un visiteur qui accepte.
describe('WAUD12 — consentement avant tout cookie', () => {
  const corpsScript = (rel: string) => read(rel).match(/<script is:inline[^>]*>([\s\S]*)<\/script>/)?.[1] ?? '';
  type Fen = Window & { fbq?: { queue: unknown[][] }; dataLayer?: unknown[][]; tqPixelTrack?: (...a: unknown[]) => void; tqGoogleTrack?: (id?: string) => void };
  const fen = window as unknown as Fen;
  const lancerCommuns = () => new Function('tqConsentDureeMs', corpsScript('../src/components/ConsentExpiry.astro'))(15552000000);
  const lancerPixel = () => new Function('tqPixelId', corpsScript('../src/components/MetaPixel.astro'))('845710231783646');
  const lancerGoogle = () =>
    new Function('tqGoogleTagIds', 'tqGoogleLeadSendTo', corpsScript('../src/components/GoogleTag.astro'))(['AW-1'], 'AW-1/x');
  const choisir = (value: string) => {
    localStorage.setItem('tq_consent', value);
    window.dispatchEvent(new CustomEvent('tq:consent-change', { detail: { value } }));
  };
  const scripts = (hote: string) => [...document.querySelectorAll('script')].filter((x) => x.src.includes(hote));
  const file = () => (fen.fbq?.queue ?? []).map((a) => [...a].slice(0, 2).join(':'));
  const couches = () => (fen.dataLayer ?? []).map((a) => [...a].slice(0, 2).join(':'));

  // Chaque script écoute `window` : on retire ses écouteurs entre deux tests.
  const ecouteurs: [string, EventListener][] = [];
  const ajouter = window.addEventListener.bind(window);

  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, 'addEventListener').mockImplementation(((t: string, f: EventListener, o?: AddEventListenerOptions) => {
      ecouteurs.push([t, f]);
      ajouter(t, f, o);
    }) as typeof window.addEventListener);
    localStorage.clear();
    document.head.innerHTML = '';
    delete fen.fbq;
    delete (fen as unknown as { _fbq?: unknown })._fbq;
    delete fen.dataLayer;
    lancerCommuns();
  });
  afterEach(() => {
    for (const [t, f] of ecouteurs.splice(0)) window.removeEventListener(t, f);
    vi.restoreAllMocks();
    vi.useRealTimers();
    localStorage.clear();
  });

  it('pixel, aucun choix : ni fbevents.js, ni init, ni PageView, file vide', () => {
    lancerPixel();
    vi.runAllTimers();
    expect(scripts('fbevents')).toEqual([]);
    expect(file()).toEqual([]);
  });

  it('pixel : jamais de revoke dans la file avant le chargement (fbevents.js s’y arrêterait, 0 /tr)', () => {
    lancerPixel();
    choisir('granted');
    expect(file()).not.toContain('consent:revoke');
    expect(file().indexOf('consent:grant')).toBeLessThan(file().indexOf('init:845710231783646'));
  });

  it('pixel, Accepter sur la page : grant, PageView, Lead en attente avec son eventId, puis fbevents.js', () => {
    lancerPixel();
    fen.tqPixelTrack?.('Lead', {}, 'ev-1');
    expect(file()).not.toContain('track:Lead');
    choisir('granted');
    expect(file()).toEqual(['consent:grant', 'init:845710231783646', 'track:PageView', 'track:Lead']);
    expect(fen.fbq?.queue.at(-1)?.[3]).toEqual({ eventID: 'ev-1' });
    window.dispatchEvent(new Event('load'));
    vi.runAllTimers();
    expect(scripts('fbevents').length).toBe(1);
  });

  it('pixel, déjà accepté : la vue part et fbevents.js se charge, différé après l’affichage', () => {
    localStorage.setItem('tq_consent', 'granted');
    lancerPixel();
    expect(file()).toContain('track:PageView');
    expect(scripts('fbevents')).toEqual([]); // jamais en synchrone dans le <head>
    window.dispatchEvent(new Event('load'));
    vi.runAllTimers();
    expect(scripts('fbevents').length).toBe(1);
  });

  it('pixel, refus : rien ; changer d’avis via « Gérer mes cookies » rallume le pixel', () => {
    localStorage.setItem('tq_consent', 'denied');
    lancerPixel();
    fen.tqPixelTrack?.('Lead', {}, 'ev-2');
    vi.runAllTimers();
    expect(scripts('fbevents')).toEqual([]);
    expect(file()).not.toContain('track:Lead');
    choisir('granted');
    window.dispatchEvent(new Event('load'));
    vi.runAllTimers();
    expect(file()).toContain('track:PageView');
    expect(scripts('fbevents').length).toBe(1);
  });

  it('pixel : refus après acceptation sur la page = revoke et plus aucun événement', () => {
    localStorage.setItem('tq_consent', 'granted');
    lancerPixel();
    choisir('denied');
    fen.tqPixelTrack?.('Lead', {}, 'ev-3');
    expect(file().at(-1)).toBe('consent:revoke');
    expect(file()).not.toContain('track:Lead');
  });

  it('Google, aucun choix : denied par défaut, ni config ni gtag.js', () => {
    lancerGoogle();
    vi.runAllTimers();
    expect(couches()).toEqual(['consent:default']);
    expect((fen.dataLayer?.[0] as unknown as unknown[])[2]).toEqual({
      ad_storage: 'denied', analytics_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
    });
    expect(scripts('googletagmanager')).toEqual([]);
  });

  it('Google, Accepter : update avant config, conversion en attente avec son eventId, puis gtag.js', () => {
    lancerGoogle();
    fen.tqGoogleTrack?.('ev-4');
    choisir('granted');
    window.dispatchEvent(new Event('load'));
    vi.runAllTimers();
    const c = couches();
    expect(c.indexOf('consent:update')).toBeLessThan(c.indexOf('config:AW-1'));
    expect(c).toContain('event:conversion');
    expect(c).toContain('event:generate_lead');
    expect(scripts('googletagmanager').length).toBe(1);
  });

  it('Google, refus : pas de chargement ; refus tardif = update denied', () => {
    localStorage.setItem('tq_consent', 'granted');
    lancerGoogle();
    choisir('denied');
    fen.tqGoogleTrack?.('ev-5');
    expect(couches().at(-1)).toBe('consent:update');
    expect((fen.dataLayer?.at(-1) as unknown as unknown[])[2]).toMatchObject({ ad_storage: 'denied' });
  });
});
