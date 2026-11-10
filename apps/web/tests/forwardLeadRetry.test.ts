import { describe, expect, it, vi } from 'vitest';
import { buildLeadRecord, forwardLead } from '../src/lib/lead';

const band = { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' as const };
const env = { LEAD_WEBHOOK_URL: 'https://crm.example/hook' };
const lead: any = {
  name: 'Test', phone: '+212600000000', city: 'Casablanca', billRange: 'gt1500',
  roofType: 'plat', consent: true,
};
const mk = () => buildLeadRecord(lead, band, new Date());
const res = (status: number) => ({ ok: status >= 200 && status < 300, status }) as Response;
const noSleep = async () => {};

describe('forwardLead — réessais (QJR631)', () => {
  it('503 puis 200 → delivered en 2 appels', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(res(503)).mockResolvedValueOnce(res(200));
    const r = await forwardLead(mk(), env, fetchFn as any, { includeUnqualified: true, sleepFn: noSleep });
    expect(r.delivered).toBe(true);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('400 → un seul appel, pas de réessai', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res(400));
    const r = await forwardLead(mk(), env, fetchFn as any, { includeUnqualified: true, sleepFn: noSleep });
    expect(r.delivered).toBe(false);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it('erreur réseau persistante → 3 tentatives puis échec', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('boom'));
    const sleeps: number[] = [];
    const r = await forwardLead(mk(), env, fetchFn as any, { includeUnqualified: true, sleepFn: async (ms) => { sleeps.push(ms); } });
    expect(r.delivered).toBe(false);
    expect(fetchFn).toHaveBeenCalledTimes(3);
    expect(sleeps).toEqual([1000, 3000]);
  });

  it('sans idempotencyKey → les appels portent la MÊME clé non vide', async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(res(503)).mockResolvedValueOnce(res(200));
    const record = mk();
    delete (record as any).idempotencyKey;
    await forwardLead(record, env, fetchFn as any, { includeUnqualified: true, sleepFn: noSleep });
    const keys = fetchFn.mock.calls.map((c) => JSON.parse(c[1].body).idempotencyKey);
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
    expect((record as any).idempotencyKey).toBeUndefined(); // copie, pas mutation
  });
});

// QJR663 — lettre morte KV (fausse liaison en mémoire).
function fakeKv() {
  const store = new Map<string, { value: string; ttl?: number }>();
  return {
    store,
    put: vi.fn(async (k: string, v: string, o?: { expirationTtl?: number; metadata?: unknown }) => { store.set(k, { value: v, ttl: o?.expirationTtl }); }),
    get: vi.fn(async (k: string) => store.get(k)?.value ?? null),
    delete: vi.fn(async (k: string) => { store.delete(k); }),
    list: vi.fn(async (o?: { prefix?: string }) => ({
      keys: [...store.keys()].filter((k) => k.startsWith(o?.prefix ?? '')).map((name) => ({ name })),
    })),
  };
}

describe('forwardLead — lettre morte KV (QJR663)', () => {
  it('503 persistant → record COMPLET déposé une seule fois, clé = idempotencyKey, avec expiration', async () => {
    const kv = fakeKv();
    const fetchFn = vi.fn().mockResolvedValue(res(503));
    const record = { ...mk(), idempotencyKey: 'idem-123' };
    const r = await forwardLead(record, { ...env, LEADS_DLQ: kv }, fetchFn as any, { includeUnqualified: true, sleepFn: noSleep });
    expect(r.delivered).toBe(false);
    expect(r.deadLettered).toBe(true);
    expect(fetchFn).toHaveBeenCalledTimes(3);
    expect(kv.put).toHaveBeenCalledTimes(1);
    const [key, value, opts] = kv.put.mock.calls[0];
    expect(key).toBe(`lead:${(record as any).idempotencyKey}`);
    expect(JSON.parse(value)).toEqual(record); // record complet
    expect(opts.expirationTtl).toBe(7 * 24 * 60 * 60);
  });

  it('record sans idempotencyKey → la clé KV porte la clé générée, présente dans le record stocké', async () => {
    const kv = fakeKv();
    const record = mk();
    delete (record as any).idempotencyKey;
    await forwardLead(record, { ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(503)) as any, { includeUnqualified: true, sleepFn: noSleep });
    const [key, value] = kv.put.mock.calls[0];
    const stored = JSON.parse(value);
    expect(stored.idempotencyKey).toBeTruthy();
    expect(key).toBe(`lead:${stored.idempotencyKey}`);
  });

  it('livré → rien déposé', async () => {
    const kv = fakeKv();
    const r = await forwardLead(mk(), { ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(200)) as any, { includeUnqualified: true, sleepFn: noSleep });
    expect(r.delivered).toBe(true);
    expect(kv.put).not.toHaveBeenCalled();
  });

  it('liaison absente → no-op gracieux (pas d\'exception, un seul avertissement sans donnée personnelle)', async () => {
    const { resetDeadLetterWarning } = await import('../worker/deadLetter.mjs');
    resetDeadLetterWarning();
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const fetchFn = vi.fn().mockResolvedValue(res(503));
    const r1 = await forwardLead(mk(), env, fetchFn as any, { includeUnqualified: true, sleepFn: noSleep });
    const r2 = await forwardLead(mk(), env, fetchFn as any, { includeUnqualified: true, sleepFn: noSleep });
    expect(r1.delivered).toBe(false);
    expect(r1.deadLettered).toBeUndefined();
    expect(r2.deadLettered).toBeUndefined();
    expect(warn).toHaveBeenCalledTimes(1);
    const logged = JSON.stringify(warn.mock.calls);
    expect(logged).not.toContain('+212600000000');
    expect(logged).not.toContain('Test');
    warn.mockRestore();
  });

  it('écriture KV en erreur → ne lève pas, deadLettered absent', async () => {
    const kv = fakeKv();
    kv.put.mockRejectedValueOnce(new Error('kv down'));
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const r = await forwardLead(mk(), { ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(503)) as any, { includeUnqualified: true, sleepFn: noSleep });
    expect(r.delivered).toBe(false);
    expect(r.deadLettered).toBeUndefined();
    warn.mockRestore();
  });
});

describe('resendDeadLetters — gestionnaire planifié (QJR663)', () => {
  it('renvoie à LEAD_WEBHOOK_URL (secret inclus) et supprime la clé sur succès ; garde sur échec', async () => {
    const { resendDeadLetters } = await import('../worker/deadLetter.mjs');
    const kv = fakeKv();
    kv.store.set('lead:a', { value: '{"idempotencyKey":"a"}' });
    kv.store.set('lead:b', { value: '{"idempotencyKey":"b"}' });
    const fetchFn = vi.fn()
      .mockResolvedValueOnce(res(200))
      .mockResolvedValueOnce(res(503));
    const log = vi.fn();
    const out = await resendDeadLetters({ ...env, LEAD_WEBHOOK_SECRET: 's3', LEADS_DLQ: kv }, fetchFn as any, log);
    expect(out).toEqual({ skipped: false, found: 2, delivered: 1, failed: 1 });
    expect(kv.store.has('lead:a')).toBe(false);
    expect(kv.store.has('lead:b')).toBe(true);
    expect(fetchFn.mock.calls[0][0]).toBe(env.LEAD_WEBHOOK_URL);
    expect(fetchFn.mock.calls[0][1].headers['x-webhook-secret']).toBe('s3');
    expect(fetchFn.mock.calls[0][1].body).toBe('{"idempotencyKey":"a"}');
    expect(JSON.stringify(log.mock.calls)).not.toContain('idempotencyKey'); // aucune donnée dans les logs
  });

  it('401 persistant → lead conservé SANS expiration sous lead-refuse: et signalé en erreur à chaque renvoi', async () => {
    const { resendDeadLetters } = await import('../worker/deadLetter.mjs');
    const kv = fakeKv();
    const record = { ...mk(), idempotencyKey: 'idem-401' };
    const r = await forwardLead(record, { ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(401)) as any,
      { includeUnqualified: true, sleepFn: noSleep });
    expect(r.deadLettered).toBe(true);
    const [key, value, opts] = kv.put.mock.calls[0];
    expect(key).toBe('lead-refuse:idem-401');
    expect(JSON.parse(value)).toEqual(record);
    expect(opts.expirationTtl).toBeUndefined();
    expect(opts.metadata).toEqual({ statut: 401 });
    // Renvois toujours à 401 : signalés en erreur, gardés ; +8 jours, le KV n'efface que les clés à TTL.
    const logError = vi.fn();
    for (let i = 0; i < 2; i++) {
      const out = await resendDeadLetters({ ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(401)) as any,
        vi.fn(), logError);
      expect(out.refused).toBe(1);
    }
    expect(logError).toHaveBeenCalledTimes(2);
    expect(logError.mock.calls[0][0]).toBe(
      '[dead-letter] 1 lead(s) refusé(s) par le CRM (HTTP 401), conservé(s) sans expiration');
    for (const [k, v] of kv.store) if (v.ttl !== undefined && v.ttl <= 8 * 24 * 3600) kv.store.delete(k);
    expect(kv.store.has('lead-refuse:idem-401')).toBe(true);
    // CRM revenu à 200 : livré puis supprimé.
    const out = await resendDeadLetters({ ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(200)) as any,
      vi.fn(), logError);
    expect(out).toEqual({ skipped: false, found: 1, delivered: 1, failed: 0 });
    expect(kv.store.has('lead-refuse:idem-401')).toBe(false);
    // Un 503 garde le chemin d'avant (lead: + 7 jours).
    const kv503 = fakeKv();
    await forwardLead({ ...mk(), idempotencyKey: 'idem-503' }, { ...env, LEADS_DLQ: kv503 },
      vi.fn().mockResolvedValue(res(503)) as any, { includeUnqualified: true, sleepFn: noSleep });
    expect(kv503.put.mock.calls[0][0]).toBe('lead:idem-503');
    expect(kv503.put.mock.calls[0][2].expirationTtl).toBe(7 * 24 * 60 * 60);
  });

  it('503 puis 401 au renvoi → déplacé sous lead-refuse: sans expiration (ADCG114)', async () => {
    const { resendDeadLetters } = await import('../worker/deadLetter.mjs');
    const kv = fakeKv();
    const record = { ...mk(), idempotencyKey: 'idem-x' };
    await forwardLead(record, { ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(503)) as any,
      { includeUnqualified: true, sleepFn: noSleep });
    expect(kv.store.get('lead:idem-x')?.ttl).toBe(7 * 24 * 60 * 60);
    // Renvoi : le CRM refuse en 401 (secret changé entre-temps).
    const logError = vi.fn();
    const out = await resendDeadLetters({ ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(401)) as any,
      vi.fn(), logError);
    expect(out).toEqual({ skipped: false, found: 1, delivered: 0, failed: 0, refused: 1 });
    expect(kv.store.has('lead:idem-x')).toBe(false);
    expect(kv.store.get('lead-refuse:idem-x')?.ttl).toBeUndefined();
    expect(JSON.parse(kv.store.get('lead-refuse:idem-x')!.value)).toEqual(record);
    const [, , opts] = kv.put.mock.calls.at(-1)!;
    expect(opts.metadata).toEqual({ statut: 401 });
    expect(logError).toHaveBeenCalledWith(
      '[dead-letter] 1 lead(s) refusé(s) par le CRM (HTTP 401), conservé(s) sans expiration');
    // +8 jours : le KV efface les clés à TTL ; le lead refusé est encore là (relecture du KV).
    for (const [k, v] of kv.store) if (v.ttl !== undefined && v.ttl <= 8 * 24 * 3600) kv.store.delete(k);
    expect(await kv.get('lead-refuse:idem-x')).not.toBeNull();
    // CRM revenu à 200 : livré puis supprimé.
    const ok = await resendDeadLetters({ ...env, LEADS_DLQ: kv }, vi.fn().mockResolvedValue(res(200)) as any,
      vi.fn(), logError);
    expect(ok).toEqual({ skipped: false, found: 1, delivered: 1, failed: 0 });
    expect(kv.store.size).toBe(0);
  });

  it('sans liaison → no-op (aucun appel réseau)', async () => {
    const { resendDeadLetters, resetDeadLetterWarning } = await import('../worker/deadLetter.mjs');
    resetDeadLetterWarning();
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const fetchFn = vi.fn();
    const out = await resendDeadLetters(env, fetchFn as any, vi.fn());
    expect(out.skipped).toBe(true);
    expect(fetchFn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});

