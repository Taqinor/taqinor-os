/**
 * WJ55/WJ109 — buildProposalTrackPayload : télémétrie PURE de vue/engagement.
 *
 * WJ109 — [régression de corruption CRM] Ce payload transitait auparavant vers
 * le webhook de CAPTURE DE LEAD (`LEAD_WEBHOOK_URL`) sous une forme
 * `{ qualified, phoneE164, utm, ... }` qui ressemblait à un lead — recevant ce
 * ping, le backend écrasait le nom réel du lead par « Lead site web ». Ce
 * garde-fou vérifie que le payload n'a PLUS jamais cette forme (aucun champ
 * `qualified`/`phoneE164`/`utm`, jamais de téléphone) et route désormais vers
 * le canal télémétrie/funnel dédié (`FUNNEL_WEBHOOK_URL`, voir
 * `pages/api/proposition-track.ts`), jamais le webhook de lead.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

vi.mock('cloudflare:workers', () => ({ env: {} }));

import { buildProposalTrackPayload } from '../src/lib/proposition';
import { corpsDeclin, declinerEndpoint, vuEndpoint } from '../src/lib/propositionSignaux';
import { POST as postVu } from '../src/pages/api/proposition-vu';
import { POST as postDecliner } from '../src/pages/api/proposition-decliner';
import { resetRateLimit } from '../src/lib/rateLimit';

const PAGE = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');

describe('ADEV98 — lecture humaine (balise) et « Décliner / demander un délai »', () => {
  const requete = (url: string, body: unknown, headers: Record<string, string> = {}) =>
    new Request(`http://localhost${url}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...headers },
      body: JSON.stringify(body),
    });
  beforeEach(() => resetRateLimit());
  afterEach(() => vi.unstubAllGlobals());

  it('endpoints backend et motifs fermés', () => {
    expect(vuEndpoint('https://api.x/', 'a b')).toBe('https://api.x/api/django/ventes/proposal/a%20b/vu/');
    expect(declinerEndpoint('https://api.x', 't')).toBe('https://api.x/api/django/ventes/proposal/t/decliner/');
    expect(corpsDeclin('prix', '  trop cher ')).toEqual({ motif: 'prix', texte: 'trop cher' });
    expect(corpsDeclin('autre', '')).toBeNull();
    expect(corpsDeclin('inconnu', 'x')).toBeNull();
  });

  it('le rendu SSR se déclare aperçu ; la page émet la balise et le formulaire de déclin', () => {
    expect(PAGE).toContain("'X-Proposition-Rendu': 'ssr'");
    expect(PAGE).toContain('installerBaliseVu(cfg.token, !!cfg.apercuInterne);');
    expect(PAGE).toContain('id="declin-form"');
  });

  it('la balise relaie User-Agent et marqueur d’équipe, et répond 204', async () => {
    const fetchMock = vi.fn(async () => ({
      status: 204,
      ok: true,
      json: async () => {
        throw new SyntaxError('corps vide');
      },
    }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const res = await postVu({
      request: requete('/api/proposition-vu', { token: 'tok' }, { 'user-agent': 'UA-humain', cookie: 'tq_equipe=1' }),
    } as never);
    expect(res.status).toBe(204);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, { headers: Record<string, string> }];
    expect(url).toMatch(/\/proposal\/tok\/vu\/$/);
    expect(init.headers['user-agent']).toBe('UA-humain');
    expect(init.headers['X-Equipe-Appareil']).toBe('1');
  });

  it('le déclin relaie le motif fermé ; un amont injoignable n’est jamais `ok: true`', async () => {
    const fetchMock = vi.fn(async () => ({
      status: 200,
      ok: true,
      json: async () => ({ detail: 'Merci', already_sent: false }),
    }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const ok = await postDecliner({ request: requete('/api/proposition-decliner', { token: 'tok', motif: 'delai' }) } as never);
    expect(ok.status).toBe(200);
    const corps = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, { body: string }])[1].body);
    expect(corps).toEqual({ motif: 'delai', texte: '' });
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new Error('panne');
    }));
    const panne = await postDecliner({ request: requete('/api/proposition-decliner', { token: 'tok', motif: 'prix' }) } as never);
    expect(panne.status).toBe(502);
    expect(((await panne.json()) as { ok: boolean }).ok).toBe(false);
  });
});

describe('WJ55/WJ109 — buildProposalTrackPayload', () => {
  it('renvoie null sans référence ni token (rien de corrélable)', () => {
    expect(buildProposalTrackPayload({ reference: '', token: '' }, 'proposal_first_view')).toBeNull();
    expect(
      buildProposalTrackPayload({ reference: '   ', token: '  ', clientPhone: '+212600000000' }, 'proposal_first_view'),
    ).toBeNull();
  });

  it('construit un payload de télémétrie PURE — jamais lead-shaped (WJ109)', () => {
    const payload = buildProposalTrackPayload(
      { reference: 'DV-042', token: 'tok42', clientPhone: '+212600000000' },
      'proposal_scrolled_financing',
    );
    expect(payload).toEqual({
      event_type: 'proposal_scrolled_financing',
      reference: 'DV-042',
      token: 'tok42',
      page: '/proposition/tok42',
    });
    // WJ109 — garde-fou explicite : jamais un champ qui ressemble à un lead.
    expect(payload).not.toHaveProperty('qualified');
    expect(payload).not.toHaveProperty('phoneE164');
    expect(payload).not.toHaveProperty('utm');
  });

  it('reste corrélable par référence seule quand le token est absent', () => {
    const payload = buildProposalTrackPayload({ reference: 'DV-099', token: '' }, 'proposal_first_view');
    expect(payload?.reference).toBe('DV-099');
  });

  it('reste corrélable par token seul quand la référence est absente', () => {
    const payload = buildProposalTrackPayload(
      { reference: '', token: 'tok99', clientPhone: '0600000000' },
      'proposal_first_view',
    );
    expect(payload?.token).toBe('tok99');
  });
});
