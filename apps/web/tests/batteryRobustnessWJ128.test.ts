// WJ128 — Robustesse prix/capacité du simulateur batterie (audit L3, findings
// 3+4). La logique PURE (resolveOfferBattery / resolveBatterySimMaxUnits /
// clamp01 via simulateBattery) est déjà couverte en détail dans
// batterySimWJ120.test.ts ; ce fichier prouve le CÂBLAGE dans le gabarit
// Astro — lecture SOURCE en texte, sans build (même convention que
// trustComponentsWJ35.test.ts / dailyCurvesCJ1.test.ts : ce rendu
// conditionnel Astro, avec ses données serveur, n'est pas facilement montable
// sous vitest).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const PAGE = read('../src/pages/proposition/[...token].astro');

describe('WJ128 (finding 3, LOW) — capacité/prix DISSOCIÉS : "sur étude" quand la capacité n’est pas sûre', () => {
  it('batteryCapacityKnown combine les TROIS sources réelles (couverture moteur / ligne du devis / batterieKwh servi ÷ unités)', () => {
    expect(PAGE).toContain('const batteryCapacityKnown =');
    expect(PAGE).toContain('batteryCoverage?.capaciteUtilePackKwh != null');
    expect(PAGE).toContain('offerBattery.capacityKwhPerUnit != null');
    expect(PAGE).toContain('servedUnitCapacityKwh != null');
  });
  it('le gabarit bascule sur batteryCapacityKnown pour choisir "N × X kWh" ou "sur étude" — jamais un chiffre catalogue deviné affiché comme sûr', () => {
    expect(PAGE).toContain('batteryCapacityKnown ? (');
    expect(PAGE).toContain('— capacité sur étude');
    expect(PAGE).toContain('— capacity on request');
    expect(PAGE).toContain('— السعة حسب الدراسة');
  });
  it('le NOMBRE d’unités (battery-sim-units) reste affiché QUELLE QUE SOIT la certitude de la capacité', () => {
    // id="battery-sim-units" est rendu AVANT le bloc conditionnel batteryCapacityKnown,
    // jamais à l'intérieur de l'une de ses deux branches.
    const idx = PAGE.indexOf('id="battery-sim-units"');
    const condIdx = PAGE.indexOf('batteryCapacityKnown ? (');
    expect(idx).toBeGreaterThan(-1);
    expect(condIdx).toBeGreaterThan(-1);
    expect(idx).toBeLessThan(condIdx);
  });
  it('le PRIX affiché (battery-sim-price) reste une question INDÉPENDANTE : jamais gaté par batteryCapacityKnown', () => {
    const priceLineIdx = PAGE.split('\n').findIndex((l) => l.includes('id="battery-sim-price"'));
    expect(priceLineIdx).toBeGreaterThan(-1);
    const priceLine = PAGE.split('\n')[priceLineIdx];
    expect(priceLine).not.toContain('batteryCapacityKnown');
    // Le prix suit sa propre règle "réel sinon Sur étude", inchangée par ce fix.
    expect(priceLine).toContain("batteryInitialPrice ?? 'Sur étude'");
  });
});

describe('WJ128 (finding 3, LOW) — le plafond du curseur passe par resolveBatterySimMaxUnits', () => {
  it('la page importe resolveBatterySimMaxUnits depuis lib/batterySim', () => {
    expect(PAGE).toMatch(/import\s*\{[^}]*resolveBatterySimMaxUnits[^}]*\}\s*from\s*'\.\.\/\.\.\/lib\/batterySim'/);
  });
  it('BATTERY_SIM_MAX_UNITS est calculé par resolveBatterySimMaxUnits(offeredUnits, storageRealMax, …) — jamais un plafond fixe (3) qui bloquerait une offre plus grande', () => {
    expect(PAGE).toContain('const BATTERY_SIM_MAX_UNITS = resolveBatterySimMaxUnits(');
    expect(PAGE).toContain('offeredUnits, storageRealMax, batteryCoverage?.nbPacksMax ?? null');
  });
});

describe('WJ128 (finding 4, LOW) — resolveOfferBattery ne retient plus la PREMIÈRE ligne qui matche BATTERY_KEYWORDS', () => {
  it('pickBestBatteryLine départage par montant (puis capacité lisible) — voir batterySimWJ120.test.ts pour la preuve comportementale', () => {
    expect(PAGE).toContain('resolveOfferBattery');
    // La fonction elle-même vit dans batterySim.ts, câblée telle quelle ici :
    // aucune re-implémentation locale de la sélection de ligne dans la page.
    expect(PAGE).not.toMatch(/for \(const it of (avec_items|sans_items)\)/);
  });
});
