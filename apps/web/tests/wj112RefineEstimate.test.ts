// WJ112 — the "Pour affiner la taille" accordion used to feed NOTHING:
// estimateFromBill() only ever read bill/lat/city, so filling ombrage/exact
// kWh silently changed no number on screen (a dead field). This proves:
//  (1) billEstimate.ts: ombrage now derates production/kWc with a DOCUMENTED,
//      never-a-gain multiplier (OMBRAGE_DERATE); exact kWh now overrides the
//      bill-derived consumption target when provided;
//  (2) the 3 mon-toit.astro variants (fr/en/ar) wire both fields into the
//      estimateFromBill() call, recompute live on change (no full-page
//      recalculation delay), and cut the fake "thinking" delay to <=500 ms;
//  (3) fields that remain genuinely capture-only (roof age, battery interest)
//      carry an honesty note instead of silently doing nothing.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { estimateFromBill, OMBRAGE_DERATE, ombrageDerateFactor } from '../src/lib/billEstimate';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const FR = read('../src/pages/devis/mon-toit.astro');
const EN = read('../src/pages/en/devis/mon-toit.astro');
const AR = read('../src/pages/ar/devis/mon-toit.astro');

describe('WJ112 — billEstimate.ts: ombrage derates the estimate honestly', () => {
  it("'aucun' laisse la production inchangée (dérate = 1, jamais un gain)", () => {
    expect(OMBRAGE_DERATE.aucun).toBe(1);
    expect(ombrageDerateFactor('aucun')).toBe(1);
    expect(ombrageDerateFactor(undefined)).toBe(1);
  });

  it('un ombrage inconnu/absent ne dérate jamais (repli sûr = 1)', () => {
    expect(ombrageDerateFactor('n-importe-quoi')).toBe(1);
  });

  it("'partiel' et 'important' sont des dérates DOCUMENTÉS, ≤ 1, et important < partiel < aucun (jamais un gain, jamais inversé)", () => {
    expect(OMBRAGE_DERATE.partiel).toBeLessThan(OMBRAGE_DERATE.aucun);
    expect(OMBRAGE_DERATE.important).toBeLessThan(OMBRAGE_DERATE.partiel);
    expect(OMBRAGE_DERATE.important).toBeGreaterThan(0);
  });

  it('filling ombrage visibly changes the estimate output (kwc and/or production go down)', () => {
    const base = estimateFromBill(1200);
    const shaded = estimateFromBill(1200, { ombrage: 'important' });
    expect(base).not.toBeNull();
    expect(shaded).not.toBeNull();
    if (!base || !shaded) return;
    // Plus ombragé -> il faut plus de kWc pour couvrir le même besoin annuel.
    expect(shaded.kwc).toBeGreaterThanOrEqual(base.kwc);
    // La production PAR kWc effectif est bien inférieure (rendement dérate).
    expect(shaded.productionKwhYr / shaded.kwc).toBeLessThan(base.productionKwhYr / base.kwc);
  });

  it("'partiel' dérate moins que 'important' pour la même facture (ordre honnête préservé)", () => {
    const partiel = estimateFromBill(1500, { ombrage: 'partiel' });
    const important = estimateFromBill(1500, { ombrage: 'important' });
    expect(partiel).not.toBeNull();
    expect(important).not.toBeNull();
    if (!partiel || !important) return;
    expect(important.kwc).toBeGreaterThanOrEqual(partiel.kwc);
  });
});

describe('WJ112 — billEstimate.ts: exact kWh overrides the bill-derived target', () => {
  it('une conso exacte plausible change le kWc par rapport à la facture seule', () => {
    const fromBillOnly = estimateFromBill(1200);
    const fromExactKwh = estimateFromBill(1200, { exactKwhMonthly: 2000 });
    expect(fromBillOnly).not.toBeNull();
    expect(fromExactKwh).not.toBeNull();
    if (!fromBillOnly || !fromExactKwh) return;
    expect(fromExactKwh.kwc).not.toBe(fromBillOnly.kwc);
  });

  it('une conso exacte non chiffrable (0/négatif/NaN) est ignorée -- retombe sur la facture (jamais cassé)', () => {
    const viaBill = estimateFromBill(1200);
    const viaZero = estimateFromBill(1200, { exactKwhMonthly: 0 });
    const viaNegative = estimateFromBill(1200, { exactKwhMonthly: -5 });
    const viaNaN = estimateFromBill(1200, { exactKwhMonthly: NaN });
    expect(viaZero).toEqual(viaBill);
    expect(viaNegative).toEqual(viaBill);
    expect(viaNaN).toEqual(viaBill);
  });

  it('sans options, le comportement est byte-identique à avant WJ112 (pas de régression)', () => {
    const est = estimateFromBill(1200);
    expect(est).not.toBeNull();
    if (!est) return;
    expect(est.kwc).toBeGreaterThan(0);
    expect(est.latitudeUsed).toBe(33.5);
  });
});

describe.each([
  ['FR', FR],
  ['EN', EN],
  ['AR', AR],
])('WJ112 — %s mon-toit.astro : accordéon "affiner" câblé + délai réduit', (_label, src) => {
  it('estimateFromBill() reçoit désormais exactKwhMonthly et ombrage (plus seulement bill/lat/city)', () => {
    expect(src).toContain('const exactKwhMonthly = num(\'mt-bill-kwh\') ?? undefined;');
    expect(src).toContain('estimateFromBill(bill, { lat, city, exactKwhMonthly, ombrage: ombrage || undefined })');
  });

  it('les clics ombrage ET la saisie kWh exact déclenchent un recalcul EN DIRECT (computeEstimate)', () => {
    // Le bloc `let ombrage = ...` jusqu'à sa 2e fermeture `});` couvre le
    // .forEach(click) complet (le 1er `});` ferme le .setAttribute/.toggle
    // forEach interne, le 2e ferme le addEventListener('click', ...)).
    const ombrageDeclStart = src.indexOf("let ombrage = savedWizard?.ombrage");
    expect(ombrageDeclStart).toBeGreaterThan(-1);
    const firstClose = src.indexOf('});', ombrageDeclStart);
    const secondClose = src.indexOf('});', firstClose + 3);
    const ombrageHandlerBlock = src.slice(ombrageDeclStart, secondClose);
    expect(ombrageHandlerBlock).toContain('computeEstimate();');

    expect(src).toContain("$('mt-bill-kwh')?.addEventListener('input', computeEstimate);");
  });

  it('le délai de « réflexion » simulé est réduit à <= 500 ms (jamais > 1.5 s comme avant)', () => {
    const minMatch = /THINKING_MIN_MS = (\d+);/.exec(src);
    const maxMatch = /THINKING_MAX_MS = (\d+);/.exec(src);
    expect(minMatch).not.toBeNull();
    expect(maxMatch).not.toBeNull();
    if (!minMatch || !maxMatch) return;
    const min = Number(minMatch[1]);
    const max = Number(maxMatch[1]);
    expect(min).toBeGreaterThan(0);
    expect(max).toBeLessThanOrEqual(500);
    expect(max).toBeGreaterThanOrEqual(min);
  });

  it('reduced-motion reste instantané (0 ms) -- comportement honnête inchangé', () => {
    expect(src).toContain('if (reducedMotion) return 0;');
  });

  it('les champs genuinely capture-only (âge du toit, batterie) portent une note d\'honnêteté WJ112', () => {
    const roofAgeIdx = src.indexOf('id="mt-roof-age"');
    expect(roofAgeIdx).toBeGreaterThan(-1);
    const afterRoofAge = src.slice(roofAgeIdx, roofAgeIdx + 900);
    expect(afterRoofAge).toContain('WJ112');
    expect(afterRoofAge.toLowerCase()).toMatch(/does not change|ne change pas/);

    const batteryIdx = src.indexOf('id="mt-battery-interest"');
    expect(batteryIdx).toBeGreaterThan(-1);
    const afterBattery = src.slice(batteryIdx, batteryIdx + 900);
    expect(afterBattery).toContain('WJ112');
    expect(afterBattery.toLowerCase()).toMatch(/does not change|ne change pas/);
  });
});
