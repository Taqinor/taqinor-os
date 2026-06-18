// Route POST /api/roof-production (W49) — fetch mocké (global), aucun réseau.
// Vérifie : validation des entrées ; mise à l'échelle par placedPanels × 0,72 ;
// le cache HIT évite tout doublon d'appel PVGIS ; pose free/building ;
// la date précise n'apparaît qu'avec la série horaire ; repli gracieux.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { POST, __clearProductionCache } from '../src/pages/api/roof-production';

function makeRequest(body: unknown): Request {
  return new Request('http://localhost/api/roof-production', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function call(body: unknown) {
  // Le handler n'utilise que `request` ; le reste du contexte Astro est inutile.
  const res = await POST({ request: makeRequest(body) } as unknown as Parameters<typeof POST>[0]);
  const json = (await (res as Response).json()) as Record<string, unknown>;
  return { status: (res as Response).status, json };
}

function okJson(payload: unknown): Response {
  return { ok: true, json: async () => payload } as unknown as Response;
}

function pvcalcResponse(monthly: number[], annual: number) {
  return okJson({
    outputs: {
      totals: { fixed: { E_y: annual } },
      monthly: { fixed: monthly.map((em, i) => ({ month: i + 1, E_m: em })) },
    },
  });
}

function seriesResponse(month: number, day: number, year: number, powerByHour: Record<number, number>) {
  const mm = String(month).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  const hourly: Array<{ time: string; P: number }> = [];
  for (let h = 0; h < 24; h++) {
    hourly.push({ time: `${year}${mm}${dd}:${String(h).padStart(2, '0')}10`, P: powerByHour[h] ?? 0 });
  }
  return okJson({ outputs: { hourly } });
}

/** Mock fetch routant PVcalc/seriescalc/DRcalc. */
function installFetch(opts: { pvcalc?: Response; series?: Response; drcalc?: Response; fail?: boolean }) {
  const fn = vi.fn().mockImplementation((url: string) => {
    if (opts.fail) return Promise.resolve({ ok: false, json: async () => ({}) } as unknown as Response);
    if (url.includes('/PVcalc')) return Promise.resolve(opts.pvcalc ?? { ok: false, json: async () => ({}) });
    if (url.includes('/seriescalc')) return Promise.resolve(opts.series ?? { ok: false, json: async () => ({}) });
    if (url.includes('/DRcalc')) return Promise.resolve(opts.drcalc ?? { ok: false, json: async () => ({}) });
    return Promise.resolve({ ok: false, json: async () => ({}) } as unknown as Response);
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

const BODY = {
  lat: 33.57,
  lon: -7.6,
  tiltDeg: 15,
  aspect: 0,
  mountingplace: 'building',
  placedPanels: 10, // → 7,2 kWc
};

describe('POST /api/roof-production — validation des entrées', () => {
  beforeEach(() => __clearProductionCache());
  afterEach(() => vi.unstubAllGlobals());

  it('JSON invalide → 400', async () => {
    const res = await POST({
      request: new Request('http://localhost/api/roof-production', { method: 'POST', body: 'not json' }),
    } as unknown as Parameters<typeof POST>[0]);
    expect((res as Response).status).toBe(400);
  });

  it('lat / lon hors plage → 400', async () => {
    installFetch({ pvcalc: pvcalcResponse(new Array(12).fill(100), 1200) });
    expect((await call({ ...BODY, lat: 999 })).status).toBe(400);
    expect((await call({ ...BODY, lon: 999 })).status).toBe(400);
  });

  it('tiltDeg / aspect invalides → 400', async () => {
    expect((await call({ ...BODY, tiltDeg: 200 })).status).toBe(400);
    expect((await call({ ...BODY, aspect: 999 })).status).toBe(400);
  });

  it('placedPanels ≤ 0 → 400', async () => {
    expect((await call({ ...BODY, placedPanels: 0 })).status).toBe(400);
    expect((await call({ ...BODY, placedPanels: -3 })).status).toBe(400);
  });
});

describe('POST /api/roof-production — mise à l’échelle et contenu', () => {
  beforeEach(() => __clearProductionCache());
  afterEach(() => vi.unstubAllGlobals());

  it('production mise à l’échelle par placedPanels × 0,72 kWc', async () => {
    installFetch({
      pvcalc: pvcalcResponse(new Array(12).fill(100), 1200),
      series: seriesResponse(1, 1, 2019, { 12: 4 }),
    });
    const { status, json } = await call(BODY);
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.source).toBe('pvgis');
    expect(json.panelKwc).toBeCloseTo(0.72, 6);
    expect(json.placedKwc).toBeCloseTo(7.2, 6);
    // Annuel par 1 kWc = 1200 → ×7,2 = 8640.
    expect(json.annualKwh as number).toBeCloseTo(8640, 3);
    expect((json.monthlyKwh as number[]).length).toBe(12);
    expect((json.typicalDayByMonth as number[][]).length).toBe(12);
    expect((json.typicalDayByMonth as number[][])[0].length).toBe(24);
  });

  it('date précise renvoyée seulement avec la série horaire', async () => {
    installFetch({
      pvcalc: pvcalcResponse(new Array(12).fill(100), 1200),
      series: seriesResponse(3, 15, 2019, { 12: 5 }),
    });
    const withDate = await call({ ...BODY, dateMonth: 3, dateDay: 15 });
    expect(withDate.json.specificDate).not.toBeNull();
    const sd = withDate.json.specificDate as { month: number; day: number; yearsAveraged: number };
    expect(sd.month).toBe(3);
    expect(sd.day).toBe(15);
    expect(sd.yearsAveraged).toBe(1);
  });

  it('sans série horaire (PVcalc + DRcalc) → pas de date précise', async () => {
    installFetch({
      pvcalc: pvcalcResponse(new Array(12).fill(100), 1200),
      drcalc: okJson({ outputs: { daily_profile: [{ month: 3, time: '12:00', 'G(i)': 700 }] } }),
    });
    const { json } = await call({ ...BODY, dateMonth: 3, dateDay: 15 });
    expect(json.specificDate).toBeNull();
  });
});

describe('POST /api/roof-production — cache : hits sans doublon d’appel PVGIS', () => {
  beforeEach(() => __clearProductionCache());
  afterEach(() => vi.unstubAllGlobals());

  it('deux requêtes sur le même plan → 1 seul lot d’appels PVGIS (2e = cacheHit)', async () => {
    const fn = installFetch({
      pvcalc: pvcalcResponse(new Array(12).fill(100), 1200),
      series: seriesResponse(1, 1, 2019, { 12: 4 }),
    });
    const first = await call(BODY);
    const callsAfterFirst = fn.mock.calls.length;
    expect(first.json.cacheHit).toBe(false);
    expect(callsAfterFirst).toBeGreaterThan(0);

    // Même plan, autre nombre de panneaux : doit servir le cache (aucun appel en plus).
    const second = await call({ ...BODY, placedPanels: 20 });
    expect(second.json.cacheHit).toBe(true);
    expect(fn.mock.calls.length).toBe(callsAfterFirst); // ZÉRO appel PVGIS supplémentaire
    // Et la mise à l’échelle suit quand même les 20 panneaux (14,4 kWc).
    expect(second.json.placedKwc as number).toBeCloseTo(14.4, 6);
    expect(second.json.annualKwh as number).toBeCloseTo(1200 * 14.4, 2);
  });

  it('plan arrondi identique (micro-déplacement) → cacheHit', async () => {
    const fn = installFetch({
      pvcalc: pvcalcResponse(new Array(12).fill(100), 1200),
      series: seriesResponse(1, 1, 2019, { 12: 4 }),
    });
    await call(BODY);
    const after = fn.mock.calls.length;
    const nudged = await call({ ...BODY, lat: 33.5703, lon: -7.6002 }); // arrondi à 3 décimales → même clé
    expect(nudged.json.cacheHit).toBe(true);
    expect(fn.mock.calls.length).toBe(after);
  });

  it('plan différent (azimut Est) → nouveau lot d’appels (pas de cacheHit)', async () => {
    const fn = installFetch({
      pvcalc: pvcalcResponse(new Array(12).fill(100), 1200),
      series: seriesResponse(1, 1, 2019, { 12: 4 }),
    });
    await call(BODY);
    const after = fn.mock.calls.length;
    const east = await call({ ...BODY, aspect: -90 });
    expect(east.json.cacheHit).toBe(false);
    expect(fn.mock.calls.length).toBeGreaterThan(after);
  });
});

describe('POST /api/roof-production — repli gracieux PVGIS injoignable', () => {
  beforeEach(() => __clearProductionCache());
  afterEach(() => vi.unstubAllGlobals());

  it('PVGIS KO → source estimate, production non nulle, jamais d’erreur', async () => {
    installFetch({ fail: true });
    const { status, json } = await call(BODY);
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.source).toBe('estimate');
    expect(json.annualKwh as number).toBeGreaterThan(0);
    expect(json.specificDate).toBeNull();
  });
});
