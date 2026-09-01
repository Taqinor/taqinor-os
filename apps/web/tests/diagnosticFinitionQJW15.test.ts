/**
 * QJW15 — LOT DE FINITION DES DEUX FORMULAIRES DIAGNOSTIC.
 *
 * Trois manques constatés, trois gardes ici :
 *
 * (a) DÉDOUBLONNAGE. Les deux formulaires n'envoyaient AUCUN jeton, contrairement
 *     au tunnel /devis/mon-toit qui génère `buildIdempotencyKey`/`buildClientRef`
 *     précisément pour ce cas. `submitBtn.disabled` protège du double-clic mais
 *     PAS d'une resoumission après rechargement de page : le CRM n'avait alors
 *     aucun signal pour fusionner les deux lignes.
 *
 * (b) `aria-invalid`. Le CSS `input[aria-invalid="true"]` existait dans les deux
 *     composants mais le script ne posait JAMAIS l'attribut : ni repérage au
 *     lecteur d'écran, ni bordure d'erreur. Règle du CSS mort.
 *
 * (c) HONEYPOT ASYMÉTRIQUE. `preview-lead.ts` appelait `isHoneypotTripped` alors
 *     qu'AUCUN des deux composants ne rendait le champ `website_url` : la garde
 *     de preview était un no-op, et `/api/simulate` (le formulaire LIVE) ne
 *     l'appelait même pas. Le champ est ajouté aux deux composants ET l'appel à
 *     simulate.ts — la garde devient réelle des deux côtés.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const mockEnv: Record<string, string> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));

import { validateLead } from '../src/lib/lead';
import { resetRateLimit } from '../src/lib/rateLimit';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const COMPOSANTS: Array<[string, string]> = [
  ['DiagnosticForm', read('../src/components/DiagnosticForm.astro')],
  ['DiagnosticFormEnriched', read('../src/components/DiagnosticFormEnriched.astro')],
];

const CRM = 'https://crm.example/hook';
const CAPI = 'https://capi.example/events';

const qualifie = {
  fullName: 'Reda K.',
  phone: '0612345678',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

// ————————————————————————————————————————————————————————————————
// (a) Jetons de dédoublonnage
// ————————————————————————————————————————————————————————————————
describe('QJW15 (a) — les deux formulaires envoient un jeton de dédoublonnage', () => {
  it.each(COMPOSANTS)('%s — réutilise buildIdempotencyKey / buildClientRef de lib/lead', (_nom, src) => {
    expect(src).toContain('buildIdempotencyKey');
    expect(src).toContain('buildClientRef');
    // …et les JOINT réellement au payload (pas seulement importés).
    expect(src).toContain('payload.idempotencyKey');
    expect(src).toContain('payload.clientRef');
  });

  it.each(COMPOSANTS)('%s — les jetons SURVIVENT à un rechargement (sinon ils ne dédoublonnent rien)', (_nom, src) => {
    // Le défaut visé n'est pas le double-clic (déjà couvert par submitBtn.disabled)
    // mais la RESOUMISSION APRÈS RECHARGEMENT : un jeton régénéré à chaque
    // chargement ne fusionnerait rien côté CRM.
    expect(src).toContain('sessionStorage');
    expect(src).toMatch(/tq_diag_idempotency|tq_diag_client_ref/);
  });

  it('validateLead accepte ces deux jetons et les transmet au CRM', () => {
    const v = validateLead({ ...qualifie, idempotencyKey: 'a'.repeat(32), clientRef: 'TQ-AB2C' });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.lead.idempotencyKey).toBe('a'.repeat(32));
    expect(v.lead.clientRef).toBe('TQ-AB2C');
  });
});

// ————————————————————————————————————————————————————————————————
// (b) aria-invalid
// ————————————————————————————————————————————————————————————————
describe('QJW15 (b) — le CSS aria-invalid n’est plus mort', () => {
  it.each(COMPOSANTS)('%s — le script POSE et RETIRE aria-invalid', (_nom, src) => {
    // Le style existait déjà des deux côtés…
    expect(src).toContain('aria-invalid="true"');
    // …mais rien ne le déclenchait : il faut la pose ET le retrait.
    expect(src).toContain("setAttribute('aria-invalid', 'true')");
    expect(src).toContain("removeAttribute('aria-invalid')");
  });
});

// ————————————————————————————————————————————————————————————————
// (c) Honeypot — la garde devient réelle
// ————————————————————————————————————————————————————————————————
describe('QJW15 (c) — le champ honeypot existe vraiment', () => {
  it.each(COMPOSANTS)('%s — rend le champ website_url, masqué et hors tabulation', (_nom, src) => {
    expect(src).toContain('name="website_url"');
    expect(src).toContain('tabindex="-1"');
    expect(src).toContain('autocomplete="off"');
  });

  it('/api/simulate importe et appelle la garde (elle n’était appelée que côté preview)', () => {
    const sim = read('../src/pages/api/simulate.ts');
    expect(sim).toContain('isHoneypotTripped');
  });
});

describe('QJW15 (c) — comportement : un bot rempli est rejeté en silence', () => {
  beforeEach(() => {
    resetRateLimit();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    mockEnv.LEAD_WEBHOOK_URL = CRM;
    mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
    mockEnv.CAPI_URL = CAPI;
  });
  afterEach(() => vi.unstubAllGlobals());

  it('/api/simulate — website_url rempli : succès factice, AUCUN appel sortant', async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        urls.push(String(url));
        return { ok: true, json: async () => ({}) } as unknown as Response;
      }),
    );
    const { POST } = await import('../src/pages/api/simulate');
    const req = new Request('http://localhost/api/simulate', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...qualifie, website_url: 'http://spam.example' }),
    });
    const res = (await POST({ request: req } as never)) as Response;
    const json = (await res.json()) as Record<string, unknown>;
    // Réponse de succès FACTICE : jamais un signal au bot sur ce qui l'a trahi.
    expect(res.status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.qualified).toBe(false);
    // …et rien n'est parti : ni CRM, ni Meta.
    expect(urls).toEqual([]);
  });

  it('/api/simulate — un visiteur humain (champ vide) passe exactement comme avant', async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        urls.push(String(url));
        return { ok: true, json: async () => ({}) } as unknown as Response;
      }),
    );
    const { POST } = await import('../src/pages/api/simulate');
    const req = new Request('http://localhost/api/simulate', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...qualifie, website_url: '' }),
    });
    const res = (await POST({ request: req } as never)) as Response;
    const json = (await res.json()) as Record<string, unknown>;
    expect(json.ok).toBe(true);
    expect(json.qualified).toBe(true);
    expect(urls).toContain(CRM);
  });
});
