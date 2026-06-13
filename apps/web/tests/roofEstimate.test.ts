// Appel serveur PVGIS (API PVcalc de la Commission européenne, sans clé,
// couvre le Maroc). Paramétré par fetchFn pour rester testable hors réseau.
// Tolère toute panne en silence → null (la route bascule alors sur le repli
// local fallbackAnnualKwh, jamais d'erreur côté visiteur).
import { describe, expect, it, vi } from 'vitest';
import { fetchPvgisAnnualKwh } from '../src/lib/roofEstimate';

/** Réponse PVGIS PVcalc minimale réaliste. */
function pvgisOk(eY: number) {
  return {
    ok: true,
    json: async () => ({ outputs: { totals: { fixed: { E_y: eY } } } }),
  } as unknown as Response;
}

describe('fetchPvgisAnnualKwh — production annuelle (kWh) via PVGIS', () => {
  it('réponse valide → renvoie E_y', async () => {
    const fetchFn = vi.fn().mockResolvedValue(pvgisOk(9123.4));
    const kwh = await fetchPvgisAnnualKwh(33.57, -7.6, 5, 0, fetchFn as unknown as typeof fetch);
    expect(kwh).toBeCloseTo(9123.4, 1);
  });

  it('construit une URL PVcalc correcte (lat, lon, peakpower, aspect, json)', async () => {
    const fetchFn = vi.fn().mockResolvedValue(pvgisOk(8000));
    await fetchPvgisAnnualKwh(33.57, -7.6, 5.5, -45, fetchFn as unknown as typeof fetch);
    const url = String((fetchFn as unknown as { mock: { calls: unknown[][] } }).mock.calls[0][0]);
    expect(url).toContain('PVcalc');
    expect(url).toContain('lat=33.57');
    expect(url).toContain('lon=-7.6');
    expect(url).toContain('peakpower=5.5');
    expect(url).toContain('aspect=-45');
    expect(url).toContain('outputformat=json');
  });

  it('statut non-OK → null (repli local)', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) } as unknown as Response);
    expect(await fetchPvgisAnnualKwh(33.57, -7.6, 5, 0, fetchFn as unknown as typeof fetch)).toBeNull();
  });

  it('exception réseau / timeout → null (jamais d’erreur propagée)', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new Error('AbortError'));
    expect(await fetchPvgisAnnualKwh(33.57, -7.6, 5, 0, fetchFn as unknown as typeof fetch)).toBeNull();
  });

  it('réponse malformée (E_y absent) → null', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ outputs: {} }) } as unknown as Response);
    expect(await fetchPvgisAnnualKwh(33.57, -7.6, 5, 0, fetchFn as unknown as typeof fetch)).toBeNull();
  });

  it('kWc ≤ 0 → null sans appel réseau (rien à estimer)', async () => {
    const fetchFn = vi.fn();
    expect(await fetchPvgisAnnualKwh(33.57, -7.6, 0, 0, fetchFn as unknown as typeof fetch)).toBeNull();
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('coordonnées hors plage → null sans appel réseau', async () => {
    const fetchFn = vi.fn();
    expect(await fetchPvgisAnnualKwh(999, -7.6, 5, 0, fetchFn as unknown as typeof fetch)).toBeNull();
    expect(await fetchPvgisAnnualKwh(33.57, 999, 5, 0, fetchFn as unknown as typeof fetch)).toBeNull();
    expect(fetchFn).not.toHaveBeenCalled();
  });
});
