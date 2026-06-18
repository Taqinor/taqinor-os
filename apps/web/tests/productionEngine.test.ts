// Moteur de DONNÉES DE PRODUCTION server-side (W49) — tests purs, fetch mocké
// (aucun réseau). Vérifie : per-kWc → mise à l'échelle linéaire ; jour-type =
// moyenne du mois ; date précise = moyenne inter-années ; réconciliation
// mensuelle/annuelle ancrée sur PVcalc ; mapping de signe d'azimut ; pose
// free/building par type de toit ; repli gracieux ; et (route) les hits de
// cache évitant les doublons d'appels PVGIS.
import { describe, expect, it, vi } from 'vitest';
import {
  PANEL_KWC,
  DAYS_IN_MONTH,
  placedKwcFromPanels,
  typicalDayFromSeries,
  specificDateFromSeries,
  buildPerKwc,
  scaleByKwc,
  scaleDateProfile,
  bellCurveShape,
  shapeFromDailyProfiles,
  fallbackPerKwc,
  cacheKeyForPlane,
  fetchPerKwcProduction,
  type ProductionPlane,
} from '../src/lib/productionEngine';
import {
  fetchPvgisMonthlySeries,
  fetchPvgisHourlySeries,
  fetchPvgisDailyProfiles,
  parseSeriesTimestamp,
  parseClockHour,
  type SeriesHourlyPoint,
  type PvcalcMonthly,
} from '../src/lib/roofEstimate';

// — Helpers de réponse PVGIS mockées ————————————————————————————————————

function okJson(payload: unknown): Response {
  return { ok: true, json: async () => payload } as unknown as Response;
}

/** Construit une réponse PVcalc avec 12 E_m + E_y. */
function pvcalcResponse(monthly: number[], annual: number) {
  return okJson({
    outputs: {
      totals: { fixed: { E_y: annual } },
      monthly: { fixed: monthly.map((em, i) => ({ month: i + 1, E_m: em })) },
    },
  });
}

/** Construit une réponse seriescalc à partir d'une liste de points {time, P}. */
function seriesResponse(points: Array<{ time: string; P: number }>) {
  return okJson({ outputs: { hourly: points } });
}

/** Génère une journée plate de N heures de jour (P watts) pour un jour donné. */
function dayHours(year: number, month: number, day: number, powerByHour: Record<number, number>) {
  const mm = String(month).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  const pts: Array<{ time: string; P: number }> = [];
  for (let h = 0; h < 24; h++) {
    const hh = String(h).padStart(2, '0');
    pts.push({ time: `${year}${mm}${dd}:${hh}10`, P: powerByHour[h] ?? 0 });
  }
  return pts;
}

// — parsing —————————————————————————————————————————————————————————————

describe('parseSeriesTimestamp / parseClockHour', () => {
  it('parse "YYYYMMDD:HHMM" en {year,month,day,hour} (heure = HH)', () => {
    expect(parseSeriesTimestamp('20200315:1410')).toEqual({ year: 2020, month: 3, day: 15, hour: 14 });
    expect(parseSeriesTimestamp('20200101:0009')).toEqual({ year: 2020, month: 1, day: 1, hour: 0 });
  });
  it('rejette les timestamps malformés', () => {
    expect(parseSeriesTimestamp('garbage')).toBeNull();
    expect(parseSeriesTimestamp('2020-03-15')).toBeNull();
    expect(parseSeriesTimestamp(1234 as unknown)).toBeNull();
    expect(parseSeriesTimestamp('20201315:1410')).toBeNull(); // mois 13
  });
  it('parse "HH:MM" DRcalc en heure décimale', () => {
    expect(parseClockHour('09:30')).toBeCloseTo(9.5, 6);
    expect(parseClockHour('00:00')).toBe(0);
    expect(parseClockHour(11)).toBe(11); // déjà nombre
    expect(Number.isNaN(parseClockHour('bad'))).toBe(true);
  });
});

// — constantes / kWc ————————————————————————————————————————————————————

describe('kWc posé (Canadian Solar 720 W)', () => {
  it('PANEL_KWC = 0,72 et placedKwcFromPanels = panneaux × 0,72', () => {
    expect(PANEL_KWC).toBeCloseTo(0.72, 6);
    expect(placedKwcFromPanels(10)).toBeCloseTo(7.2, 6);
    expect(placedKwcFromPanels(0)).toBe(0);
    expect(placedKwcFromPanels(-5)).toBe(0);
  });
});

// — jour type = moyenne du mois ————————————————————————————————————————

describe('typicalDayFromSeries — jour type = moyenne du mois sur toutes les années', () => {
  it('moyenne heure-par-heure sur tous les jours/années du mois (W → kW)', () => {
    // Mois 6 : 2 jours sur 2 ans = 2 échantillons par heure.
    const series: SeriesHourlyPoint[] = [
      ...dayHours(2018, 6, 1, { 12: 1000 }).map((p) => ({ ...parseSeriesTimestamp(p.time)!, powerW: p.P })),
      ...dayHours(2019, 6, 1, { 12: 2000 }).map((p) => ({ ...parseSeriesTimestamp(p.time)!, powerW: p.P })),
    ];
    const prof = typicalDayFromSeries(series, 6);
    expect(prof).toHaveLength(24);
    // Midi : moyenne (1000 + 2000)/2 = 1500 W → 1,5 kW.
    expect(prof[12]).toBeCloseTo(1.5, 6);
    // Nuit : 0.
    expect(prof[0]).toBe(0);
  });

  it('mois absent → profil tout à zéro', () => {
    const series: SeriesHourlyPoint[] = dayHours(2018, 6, 1, { 12: 1000 }).map((p) => ({
      ...parseSeriesTimestamp(p.time)!,
      powerW: p.P,
    }));
    expect(typicalDayFromSeries(series, 3)).toEqual(new Array(24).fill(0));
  });
});

// — date précise = moyenne inter-années ————————————————————————————————

describe('specificDateFromSeries — date précise moyennée sur les années disponibles', () => {
  it('« 15 mars type » = moyenne du 15 mars sur 3 ans (jamais une seule année)', () => {
    const series: SeriesHourlyPoint[] = [
      ...dayHours(2018, 3, 15, { 12: 900 }),
      ...dayHours(2019, 3, 15, { 12: 1200 }),
      ...dayHours(2020, 3, 15, { 12: 900 }),
      // bruit : autres dates, ne doivent pas compter
      ...dayHours(2018, 3, 16, { 12: 5000 }),
    ].map((p) => ({ ...parseSeriesTimestamp(p.time)!, powerW: p.P }));

    const prof = specificDateFromSeries(series, 3, 15);
    expect(prof.yearsAveraged).toBe(3);
    // Midi : (900 + 1200 + 900)/3 = 1000 W → 1 kW.
    expect(prof.hourlyKw[12]).toBeCloseTo(1.0, 6);
    // Total journalier (pas horaire 1 h) = somme = 1 kWh ici.
    expect(prof.dailyKwh).toBeCloseTo(1.0, 6);
  });

  it('date absente → 0 année moyennée, profil nul', () => {
    const series: SeriesHourlyPoint[] = dayHours(2018, 3, 15, { 12: 900 }).map((p) => ({
      ...parseSeriesTimestamp(p.time)!,
      powerW: p.P,
    }));
    const prof = specificDateFromSeries(series, 7, 4);
    expect(prof.yearsAveraged).toBe(0);
    expect(prof.dailyKwh).toBe(0);
  });
});

// — réconciliation mensuelle/annuelle ancrée sur PVcalc ————————————————

describe('buildPerKwc — réconciliation : jour-type → journalier → mensuel = PVcalc', () => {
  const monthly = [120, 130, 160, 170, 185, 195, 205, 200, 175, 155, 125, 110];
  const annual = monthly.reduce((a, b) => a + b, 0);
  const pvcalc: PvcalcMonthly = { annualKwh: annual, monthlyKwh: monthly };

  it('mensuel renvoyé = PVcalc exactement (ancre)', () => {
    const series = [
      ...dayHours(2019, 6, 1, { 10: 0.3, 12: 0.6, 14: 0.3 }),
      ...dayHours(2019, 6, 2, { 10: 0.3, 12: 0.6, 14: 0.3 }),
    ].map((p) => ({ ...parseSeriesTimestamp(p.time)!, powerW: p.P }));
    const built = buildPerKwc(pvcalc, series, null)!;
    expect(built.source).toBe('pvgis');
    expect(built.monthlyKwh).toEqual(monthly);
    expect(built.annualKwh).toBeCloseTo(annual, 6);
  });

  it('jour-type intégré × jours du mois = total mensuel PVcalc (recalage)', () => {
    // Forme arbitraire sur juin (mois 6) ; le recalage doit forcer le total.
    const series = dayHours(2019, 6, 1, { 9: 5, 12: 9, 15: 4 }).map((p) => ({
      ...parseSeriesTimestamp(p.time)!,
      powerW: p.P,
    }));
    const built = buildPerKwc(pvcalc, series, null)!;
    const juneDaily = built.dailyKwhByMonth[5];
    const sumJune = built.typicalDayByMonth[5].reduce((a, b) => a + b, 0);
    expect(sumJune).toBeCloseTo(juneDaily, 6);
    expect(juneDaily * DAYS_IN_MONTH[5]).toBeCloseTo(monthly[5], 4);
  });

  it('cohérence globale : Σ(journalier × jours) = annuel PVcalc', () => {
    // Donne une forme à chaque mois.
    const series: SeriesHourlyPoint[] = [];
    for (let m = 1; m <= 12; m++) {
      series.push(
        ...dayHours(2019, m, 1, { 10: 1, 12: 2, 14: 1 }).map((p) => ({
          ...parseSeriesTimestamp(p.time)!,
          powerW: p.P,
        })),
      );
    }
    const built = buildPerKwc(pvcalc, series, null)!;
    const recomposed = built.dailyKwhByMonth.reduce((acc, d, m) => acc + d * DAYS_IN_MONTH[m], 0);
    expect(recomposed).toBeCloseTo(annual, 3);
  });

  it('PVcalc manquant → null (l’appelant bascule sur le repli)', () => {
    expect(buildPerKwc(null, null, null)).toBeNull();
  });

  it('PVcalc seul (ni série ni DRcalc) → source pvgis-monthly, totaux préservés', () => {
    const built = buildPerKwc(pvcalc, null, null)!;
    expect(built.source).toBe('pvgis-monthly');
    expect(built.monthlyKwh).toEqual(monthly);
    // Jour-type reconstruit par cloche, recalé : Σ × jours = mensuel.
    expect(built.dailyKwhByMonth[5] * DAYS_IN_MONTH[5]).toBeCloseTo(monthly[5], 4);
  });

  it('DRcalc en repli de forme (pas de série) → source pvgis, recalée sur PVcalc', () => {
    const drProfiles = [
      { month: 6, hour: 9, gi: 200 },
      { month: 6, hour: 12, gi: 800 },
      { month: 6, hour: 15, gi: 300 },
    ];
    const built = buildPerKwc(pvcalc, null, drProfiles)!;
    expect(built.source).toBe('pvgis');
    expect(built.dailyKwhByMonth[5] * DAYS_IN_MONTH[5]).toBeCloseTo(monthly[5], 4);
  });
});

// — mise à l'échelle linéaire ——————————————————————————————————————————

describe('scaleByKwc — per-kWc → mis à l’échelle, strictement linéaire', () => {
  const monthly = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10];
  const pvcalc: PvcalcMonthly = { annualKwh: 120, monthlyKwh: monthly };
  const series = dayHours(2019, 6, 1, { 12: 1 }).map((p) => ({ ...parseSeriesTimestamp(p.time)!, powerW: p.P }));
  const perKwc = buildPerKwc(pvcalc, series, null)!;

  it('×6 kWc multiplie annuel, mensuel, jour-type et journalier par 6', () => {
    const scaled = scaleByKwc(perKwc, 6);
    expect(scaled.placedKwc).toBe(6);
    expect(scaled.annualKwh).toBeCloseTo(perKwc.annualKwh * 6, 6);
    expect(scaled.monthlyKwh[5]).toBeCloseTo(perKwc.monthlyKwh[5] * 6, 6);
    expect(scaled.dailyKwhByMonth[5]).toBeCloseTo(perKwc.dailyKwhByMonth[5] * 6, 6);
    expect(scaled.typicalDayByMonth[5][12]).toBeCloseTo(perKwc.typicalDayByMonth[5][12] * 6, 6);
  });

  it('linéarité : à 2 kWc = 2× la valeur à 1 kWc', () => {
    const s1 = scaleByKwc(perKwc, 1);
    const s2 = scaleByKwc(perKwc, 2);
    expect(s2.annualKwh).toBeCloseTo(2 * s1.annualKwh, 6);
  });

  it('placedKwc ≤ 0 → tout à zéro', () => {
    const scaled = scaleByKwc(perKwc, 0);
    expect(scaled.annualKwh).toBe(0);
    expect(scaled.monthlyKwh.every((v) => v === 0)).toBe(true);
  });

  it('scaleDateProfile met la date à l’échelle linéairement', () => {
    const date = specificDateFromSeries(series, 6, 1);
    const scaled = scaleDateProfile(date, 4);
    expect(scaled.dailyKwh).toBeCloseTo(date.dailyKwh * 4, 6);
    expect(scaled.hourlyKw[12]).toBeCloseTo(date.hourlyKw[12] * 4, 6);
  });
});

// — formes auxiliaires ——————————————————————————————————————————————————

describe('bellCurveShape / shapeFromDailyProfiles', () => {
  it('la cloche est normalisée (somme = 1), nulle la nuit, max vers midi', () => {
    const shape = bellCurveShape();
    expect(shape).toHaveLength(24);
    expect(shape.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 6);
    expect(shape[0]).toBe(0);
    expect(shape[3]).toBe(0);
    const max = Math.max(...shape);
    const peakHour = shape.indexOf(max);
    expect(peakHour).toBeGreaterThanOrEqual(11);
    expect(peakHour).toBeLessThanOrEqual(14);
  });

  it('shapeFromDailyProfiles range G(i) par mois et heure entière', () => {
    const profiles = [
      { month: 1, hour: 12, gi: 500 },
      { month: 1, hour: 13, gi: 400 },
      { month: 6, hour: 12, gi: 900 },
    ];
    const shapes = shapeFromDailyProfiles(profiles);
    expect(shapes).toHaveLength(12);
    expect(shapes[0][12]).toBe(500);
    expect(shapes[0][13]).toBe(400);
    expect(shapes[5][12]).toBe(900);
    expect(shapes[2][12]).toBe(0); // mois sans donnée
  });
});

// — repli gracieux ————————————————————————————————————————————————————

describe('fallbackPerKwc — repli interne « estimé », clairement étiqueté', () => {
  it('source = estimate, annuel = rendement spécifique, Σ mensuel = annuel', () => {
    const fb = fallbackPerKwc(1600);
    expect(fb.source).toBe('estimate');
    expect(fb.annualKwh).toBeCloseTo(1600, 6);
    const sumMonthly = fb.monthlyKwh.reduce((a, b) => a + b, 0);
    expect(sumMonthly).toBeCloseTo(1600, 3);
  });

  it('jours types cohérents : Σ(journalier × jours) = annuel', () => {
    const fb = fallbackPerKwc(1500);
    const recomposed = fb.dailyKwhByMonth.reduce((acc, d, m) => acc + d * DAYS_IN_MONTH[m], 0);
    expect(recomposed).toBeCloseTo(1500, 2);
  });
});

// — clé de cache ————————————————————————————————————————————————————————

describe('cacheKeyForPlane — arrondit pour regrouper les re-rendus', () => {
  it('mêmes lat/lon/tilt/azimut arrondis + pose → même clé', () => {
    const a: ProductionPlane = { lat: 33.5712, lon: -7.6001, tiltDeg: 15.2, aspect: 0.4, mountingplace: 'building' };
    const b: ProductionPlane = { lat: 33.5714, lon: -7.5996, tiltDeg: 14.8, aspect: -0.3, mountingplace: 'building' };
    expect(cacheKeyForPlane(a)).toBe(cacheKeyForPlane(b));
  });
  it('pose free vs building → clés distinctes', () => {
    const free: ProductionPlane = { lat: 33.5, lon: -7.6, tiltDeg: 10, aspect: 0, mountingplace: 'free' };
    const building: ProductionPlane = { ...free, mountingplace: 'building' };
    expect(cacheKeyForPlane(free)).not.toBe(cacheKeyForPlane(building));
  });
  it('azimut différent → clé différente', () => {
    const south: ProductionPlane = { lat: 33.5, lon: -7.6, tiltDeg: 15, aspect: 0, mountingplace: 'building' };
    const east: ProductionPlane = { ...south, aspect: -90 };
    expect(cacheKeyForPlane(south)).not.toBe(cacheKeyForPlane(east));
  });
});

// — mapping de signe d'azimut (helpers roofEstimate, fetch mocké) ————————

describe('azimut PVGIS : Sud=0, Est=−90, Ouest=+90, Nord=180 (transmis à PVGIS)', () => {
  it('fetchPvgisMonthlySeries transmet aspect tel quel dans l’URL', async () => {
    const monthly = new Array(12).fill(100);
    const fetchFn = vi.fn().mockResolvedValue(pvcalcResponse(monthly, 1200));
    await fetchPvgisMonthlySeries(33.57, -7.6, 1, -90, 15, fetchFn as unknown as typeof fetch);
    const url = String(fetchFn.mock.calls[0][0]);
    expect(url).toContain('PVcalc');
    expect(url).toContain('aspect=-90'); // Est
    expect(url).toContain('peakpower=1'); // interrogé par 1 kWc
  });

  it('fetchPvgisHourlySeries transmet aspect +90 (Ouest) et pvcalculation=1', async () => {
    const fetchFn = vi.fn().mockResolvedValue(seriesResponse(dayHours(2019, 1, 1, { 12: 500 })));
    await fetchPvgisHourlySeries(33.57, -7.6, 1, 90, 15, 2016, 2020, fetchFn as unknown as typeof fetch);
    const url = String(fetchFn.mock.calls[0][0]);
    expect(url).toContain('seriescalc');
    expect(url).toContain('aspect=90'); // Ouest
    expect(url).toContain('pvcalculation=1');
    expect(url).toContain('startyear=2016');
    expect(url).toContain('endyear=2020');
  });
});

// — pose free vs building par type de toit ——————————————————————————————

describe('mounting "free" (toit plat racké) vs "building" (pitched) transmis à PVGIS', () => {
  it('building par défaut', async () => {
    const fetchFn = vi.fn().mockResolvedValue(pvcalcResponse(new Array(12).fill(100), 1200));
    await fetchPvgisMonthlySeries(33.57, -7.6, 1, 0, 15, fetchFn as unknown as typeof fetch);
    expect(String(fetchFn.mock.calls[0][0])).toContain('mountingplace=building');
  });
  it('free quand demandé (toit plat)', async () => {
    const fetchFn = vi.fn().mockResolvedValue(seriesResponse(dayHours(2019, 1, 1, { 12: 500 })));
    await fetchPvgisHourlySeries(33.57, -7.6, 1, 0, 5, 2016, 2020, fetchFn as unknown as typeof fetch, 'free');
    expect(String(fetchFn.mock.calls[0][0])).toContain('mountingplace=free');
  });
});

// — orchestration : fetchPerKwcProduction (fetch mocké) ————————————————

describe('fetchPerKwcProduction — combinaison minimale et repli', () => {
  function routeFetch(handlers: { pvcalc?: Response; series?: Response; drcalc?: Response }) {
    return vi.fn().mockImplementation((url: string) => {
      if (url.includes('/PVcalc')) return Promise.resolve(handlers.pvcalc ?? { ok: false, json: async () => ({}) });
      if (url.includes('/seriescalc')) return Promise.resolve(handlers.series ?? { ok: false, json: async () => ({}) });
      if (url.includes('/DRcalc')) return Promise.resolve(handlers.drcalc ?? { ok: false, json: async () => ({}) });
      return Promise.resolve({ ok: false, json: async () => ({}) });
    });
  }
  const plane: ProductionPlane = { lat: 33.57, lon: -7.6, tiltDeg: 15, aspect: 0, mountingplace: 'building' };

  it('PVcalc + seriescalc disponibles → source pvgis, série conservée', async () => {
    const monthly = new Array(12).fill(100);
    const fetchFn = routeFetch({
      pvcalc: pvcalcResponse(monthly, 1200),
      series: seriesResponse([...dayHours(2019, 1, 1, { 12: 4 }), ...dayHours(2020, 1, 1, { 12: 4 })]),
    });
    const { perKwc, series } = await fetchPerKwcProduction(plane, 2016, 2020, fetchFn as unknown as typeof fetch);
    expect(perKwc.source).toBe('pvgis');
    expect(series).not.toBeNull();
    // PVcalc et seriescalc appelés ; DRcalc PAS appelé (série OK).
    const urls = fetchFn.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes('/PVcalc'))).toBe(true);
    expect(urls.some((u) => u.includes('/seriescalc'))).toBe(true);
    expect(urls.some((u) => u.includes('/DRcalc'))).toBe(false);
  });

  it('série KO mais PVcalc OK → DRcalc sollicité (repli de forme), source pvgis', async () => {
    const fetchFn = routeFetch({
      pvcalc: pvcalcResponse(new Array(12).fill(100), 1200),
      series: { ok: false, json: async () => ({}) } as unknown as Response,
      drcalc: okJson({ outputs: { daily_profile: [{ month: 1, time: '12:00', 'G(i)': 700 }] } }),
    });
    const { perKwc, series } = await fetchPerKwcProduction(plane, 2016, 2020, fetchFn as unknown as typeof fetch);
    expect(perKwc.source).toBe('pvgis');
    expect(series).toBeNull();
    expect(fetchFn.mock.calls.some((c) => String(c[0]).includes('/DRcalc'))).toBe(true);
  });

  it('PVGIS totalement injoignable → repli interne estimate', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) } as unknown as Response);
    const { perKwc, series } = await fetchPerKwcProduction(plane, 2016, 2020, fetchFn as unknown as typeof fetch);
    expect(perKwc.source).toBe('estimate');
    expect(series).toBeNull();
    expect(perKwc.annualKwh).toBeGreaterThan(0);
  });

  it('fetchPvgisDailyProfiles tolère le JSON malformé → null', async () => {
    const fetchFn = vi.fn().mockResolvedValue(okJson({ outputs: {} }));
    expect(await fetchPvgisDailyProfiles(33.57, -7.6, 0, 15, fetchFn as unknown as typeof fetch)).toBeNull();
  });
});
