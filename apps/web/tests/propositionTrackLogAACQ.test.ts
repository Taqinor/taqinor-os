// AACQ42 (C-AACQ-042) — le journal de `/api/proposition-track` ne contient
// jamais le jeton porteur de la proposition (ni en `token`, ni dans `page`),
// ni la référence complète, ni `appareil_id`. Le corps envoyé au webhook
// funnel (`FUNNEL_WEBHOOK_URL`) reste octet-identique à
// `buildProposalTrackPayload`. La VRAIE route est appelée ; `console.log` et
// `fetch` sont observés en sortie (I/O, jamais le source).
//
// Test-du-test : remettre `JSON.stringify(payload)` dans le `console.log` ⇒
// « journal sans jeton » rouge.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockEnv: Record<string, string> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));

import { POST } from '../src/pages/api/proposition-track';
import { buildProposalTrackPayload } from '../src/lib/proposition';
import { resetRateLimit } from '../src/lib/rateLimit';

// 43 caractères (comme secrets.token_urlsafe(32)), finissant par secretTAIL13.
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456secretTAIL13'.slice(-43);
const REFERENCE = 'DEV-202610-0042';
const APPAREIL = '3f0c1e8a-7b21-4a5e-9c3d-2b4f6a8e1d20';

function requete(): Request {
  return new Request('http://localhost/api/proposition-track', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'sec-fetch-site': 'same-origin' },
    body: JSON.stringify({
      token: TOKEN,
      reference: REFERENCE,
      clientPhone: '+212600000042',
      appareilId: APPAREIL,
      event: 'proposal_first_view',
    }),
  });
}

function journal(spy: ReturnType<typeof vi.spyOn>): string {
  return spy.mock.calls.map((args) => args.map((a) => String(a)).join(' ')).join('\n');
}

describe('proposition-track — journal sans jeton (AACQ42)', () => {
  let logSpy: ReturnType<typeof vi.spyOn>;
  let infoSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    resetRateLimit();
    logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function toutLeJournal(): string {
    return [logSpy, infoSpy, warnSpy, errorSpy].map(journal).join('\n');
  }

  it('journal sans jeton', async () => {
    expect(TOKEN).toHaveLength(43);
    expect(TOKEN.endsWith('secretTAIL13')).toBe(true);
    const res = await POST({ request: requete() } as never);
    expect(res.status).toBe(202);
    const sortie = journal(logSpy);
    expect(sortie).toContain('[proposition-track]');
    const tout = toutLeJournal();
    expect(tout).not.toContain(TOKEN);
    expect(tout).not.toContain('secretTAIL13');
    expect(tout).not.toContain(REFERENCE);
    expect(tout).not.toContain(APPAREIL);
    expect(tout).not.toContain('appareil_id');
    // Garde event_type et la page masquée « …<6 derniers> ».
    expect(sortie).toContain('proposal_first_view');
    expect(sortie).toContain(`/proposition/…${TOKEN.slice(-6)}`);
  });

  it('corps funnel inchangé', async () => {
    mockEnv.FUNNEL_WEBHOOK_URL = 'https://funnel.example/hook';
    const corps: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: { body?: string }) => {
        if (init?.body) corps.push(init.body);
        return new Response(null, { status: 200 });
      }),
    );
    const res = await POST({ request: requete() } as never);
    expect(res.status).toBe(200);
    expect(corps).toHaveLength(1);
    const attendu = JSON.stringify(
      buildProposalTrackPayload({ reference: REFERENCE, token: TOKEN }, 'proposal_first_view', APPAREIL),
    );
    expect(corps[0]).toBe(attendu);
    expect(toutLeJournal()).not.toContain(TOKEN);
  });
});
