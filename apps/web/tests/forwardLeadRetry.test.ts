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

