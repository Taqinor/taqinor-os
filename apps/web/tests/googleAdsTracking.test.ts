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
import { fileURLToPath } from 'node:url';
import { describe, expect, it, vi } from 'vitest';
import { parseGoogleTagIds, parseLeadSendTo } from '../src/lib/googleTag';
import { buildLeadRecord, forwardLead, runSimulation, validateLead } from '../src/lib/lead';
import { etatVide } from '../src/lib/tunnel/champs';
import { construireCorps } from '../src/lib/tunnel/corps';
import { CONTENT_SECURITY_POLICY } from '../worker/headers.mjs';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

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

  it('consentement : refus ⇒ pas de chargement ; refus tardif ⇒ consent update denied', () => {
    expect(src).toContain("localStorage.getItem('tq_consent') === 'denied'");
    expect(src).toContain("if (denied) return;");
    expect(src).toContain("window.gtag('consent', 'update'");
    for (const k of ['ad_storage', 'analytics_storage', 'ad_user_data', 'ad_personalization']) {
      expect(src).toContain(`${k}: 'denied'`);
    }
  });

  it('tqGoogleTrack : conversion Ads (si send_to) + generate_lead, transaction_id = eventId', () => {
    expect(src).toContain('window.tqGoogleTrack = function (eventId)');
    expect(src).toContain("window.gtag('event', 'conversion'");
    expect(src).toContain("window.gtag('event', 'generate_lead'");
    expect(src).toContain('transaction_id: String(eventId)');
  });

  it('inclus dans le Layout avec la même exclusion noindex que MetaPixel', () => {
    const layout = read('../src/layouts/Layout.astro');
    expect(layout).toContain('{!noindex && <MetaPixel />}');
    expect(layout).toContain('{!noindex && <GoogleTag />}');
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
    expect(directive('frame-src')).toBe("frame-src 'self' https://www.googletagmanager.com");
  });
});
