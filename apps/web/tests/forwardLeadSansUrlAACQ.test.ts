// AACQ41 — un Worker sans LEAD_WEBHOOK_URL ne jette plus le lead : lettre morte
// KV, alerte en production, renvoi après rétablissement de l'URL.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockEnv: Record<string, unknown> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));

import { resetRateLimit } from '../src/lib/rateLimit';
import { resetForwardLeadFailureStreak, trackForwardLeadOutcome } from '../src/lib/lead';
// @ts-expect-error — module .mjs sans déclaration de types
import { resendDeadLetters, resetDeadLetterWarning } from '../worker/deadLetter.mjs';

function fakeKv() {
  const store = new Map<string, string>();
  const put = vi.fn(async (k: string, v: string) => {
    store.set(k, v);
  });
  return {
    store,
    put,
    get: async (k: string) => store.get(k) ?? null,
    delete: async (k: string) => {
      store.delete(k);
    },
    list: async ({ prefix }: { prefix: string }) => ({
      keys: [...store.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })),
    }),
  };
}

const qualified = {
  fullName: 'Reda K.',
  phone: '0612345678',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

async function post(i: number) {
  const { POST } = await import('../src/pages/api/capture-lead');
  const req = new Request('http://localhost/api/capture-lead', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ ...qualified, phone: `06123456${10 + i}` }),
  });
  const res = (await POST({ request: req } as unknown as Parameters<typeof POST>[0])) as Response;
  return (await res.json()) as Record<string, unknown>;
}

describe('AACQ41 — forwardLead sans LEAD_WEBHOOK_URL', () => {
  let kv: ReturnType<typeof fakeKv>;
  beforeEach(() => {
    resetRateLimit();
    resetForwardLeadFailureStreak();
    resetDeadLetterWarning();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    kv = fakeKv();
    mockEnv.LEADS_DLQ = kv;
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('dépose en lettre morte sans URL (absente puis « blanche »)', async () => {
    const r1 = await post(1);
    mockEnv.LEAD_WEBHOOK_URL = '   ';
    const r2 = await post(2);
    const r3 = await post(3);
    expect(r1.ok).toBe(true);
    expect(r2.qualified).toBe(true);
    expect(r3.ok).toBe(true);
    expect(kv.put).toHaveBeenCalledTimes(3);
    expect(kv.store.size).toBe(3);
    for (const [k, v] of kv.store) {
      expect(k.startsWith('lead:')).toBe(true);
      expect(JSON.parse(v).idempotencyKey).toBe(k.slice(5));
    }
  });

  it('alerte en production au seuil, jamais en développement', async () => {
    vi.stubEnv('PROD', true);
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'log').mockImplementation(() => {});
    await post(1);
    await post(2);
    expect(err.mock.calls.some((c) => String(c[0]).includes('[capture-lead][ALERT]'))).toBe(false);
    await post(3);
    expect(err.mock.calls.some((c) => String(c[0]).includes('[capture-lead][ALERT]'))).toBe(true);
    resetForwardLeadFailureStreak();
    expect(trackForwardLeadOutcome(false, 'no-webhook-configured', false).streak).toBe(0);
    expect(trackForwardLeadOutcome(false, 'no-webhook-configured', true).streak).toBe(1);
  });

  it('sans liaison LEADS_DLQ : comportement historique (rien déposé)', async () => {
    delete mockEnv.LEADS_DLQ;
    const r = await post(1);
    expect(r.ok).toBe(true);
    expect(kv.put).not.toHaveBeenCalled();
  });

  it('renvoi après rétablissement : 3 livrés, KV vidé', async () => {
    await post(1);
    await post(2);
    await post(3);
    expect(kv.store.size).toBe(3);
    const sent: Array<Record<string, unknown>> = [];
    const fetchFn = vi.fn(async (_u: string, init: { body: string }) => {
      sent.push(JSON.parse(init.body));
      return { ok: true, status: 200 } as Response;
    });
    const out = await resendDeadLetters(
      { LEADS_DLQ: kv, LEAD_WEBHOOK_URL: 'https://crm.example/hook' },
      fetchFn,
      () => {},
    );
    expect(out).toMatchObject({ found: 3, delivered: 3 });
    expect(sent).toHaveLength(3);
    expect(sent.every((s) => typeof s.idempotencyKey === 'string' && s.idempotencyKey)).toBe(true);
    expect(kv.store.size).toBe(0);
  });
});
