// ACAL173 (C-ACAL-063) — le simulateur de repli de la proposition lit le
// rendement aller-retour et le DoD de la FICHE de la batterie vendue
// (`fiche_batterie`, contrat ACAL10 `couverture_batterie.json`). Fiche muette
// sur le rendement ⇒ AUCUNE simulation, l'omission nommée servie à la place —
// jamais 0,96 one-way / 0,9216 aller-retour de repli (constante SUPPRIMÉE).
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import * as batterySim from './batterySim';
import {
  batterySimParamsFromFiche,
  MOTIF_SIMULATION_OMISE,
  readFicheBatterie,
  simulateBattery,
  type BatterySimInput,
} from './batterySim';

const CONTRAT = JSON.parse(readFileSync(new URL(
  '../../../../backend/django_core/apps/ventes/contract_samples/couverture_batterie.json',
  import.meta.url), 'utf-8')) as {
  exemple: Record<string, unknown>;
  exemple_autonomie_atteignable: Record<string, unknown>;
};

// Conso 100 % à 20 h, production 100 % à 12 h : tout ce que la batterie
// restitue le soir a été stocké à midi — le bilan se vérifie à la main.
const cons = new Array(24).fill(0);
cons[20] = 1;
const prod = new Array(24).fill(0);
prod[12] = 1;
const base: Omit<BatterySimInput, 'oneWayEfficiency' | 'depthOfDischarge'> = {
  consumptionShape: cons,
  productionShape: prod,
  dailyConsumptionKwh: 10,
  dailyProductionKwh: 10,
  capacityKwhPerUnit: 20, // banque assez grande : aucun écrêtage de capacité
  units: 1,
};

describe('ACAL173 — utilise le rendement et le DoD servis', () => {
  it('« utilise le rendement et le DoD servis » : 94 % / 90 % ⇒ one-way √0,94, DoD 0,90 (parité Python/TS)', () => {
    const fiche = readFicheBatterie({
      fiche_batterie: {
        rendement_ar_pct: 94.0, dod_pct: 90, source: 'fiche',
        simulation_omise_motif: null,
      },
    });
    expect(fiche).toEqual({
      rendementArPct: 94, dodPct: 90, source: 'fiche', simulationOmiseMotif: null,
    });
    const params = batterySimParamsFromFiche(fiche);
    expect(params.ok).toBe(true);
    if (!params.ok) return;
    expect(params.oneWayEfficiency).toBeCloseTo(Math.sqrt(0.94), 12);
    expect(params.depthOfDischarge).toBeCloseTo(0.9, 12);
    const r = simulateBattery({ ...base, ...params });
    // DoD de la fiche : capacité utile = unités × capacité × 0,90.
    expect(r.usableCapacityKwh).toBeCloseTo(20 * 0.9, 9);
    // Parité avec le moteur Python (`rendement_ar` appliqué au kWh stocké) :
    // restitué = prélevé du surplus × 0,94 — le rendement ALLER-RETOUR de la
    // fiche, jamais 0,9216.
    expect(r.fromBatteryKwh).toBeCloseTo(r.solarToBatteryKwh * 0.94, 9);
    expect(r.fromBatteryKwh).not.toBeCloseTo(r.solarToBatteryKwh * 0.9216, 3);
  });

  it('DoD non publié ⇒ le repli DoD de la page (hors défaut, inchangé)', () => {
    const params = batterySimParamsFromFiche(readFicheBatterie({
      fiche_batterie: {
        rendement_ar_pct: 94, dod_pct: null, source: 'fiche',
        simulation_omise_motif: null,
      },
    }));
    expect(params.ok).toBe(true);
    if (!params.ok) return;
    expect(params.depthOfDischarge).toBeUndefined();
    const r = simulateBattery({ ...base, ...params });
    expect(r.usableCapacityKwh).toBeCloseTo(20 * batterySim.BATTERY_DEPTH_OF_DISCHARGE, 9);
  });
});

describe('ACAL173 — sans rendement fourni : aucune simulation, omission nommée', () => {
  it('« sans rendement fourni : aucune simulation, omission nommée »', () => {
    const fiche = readFicheBatterie({ fiche_batterie: CONTRAT.exemple.fiche_batterie });
    expect(fiche?.rendementArPct).toBeNull();
    const params = batterySimParamsFromFiche(fiche);
    expect(params).toEqual({
      ok: false,
      motif: 'Rendement aller-retour non publié par la fiche de la batterie : simulation omise',
    });
  });

  it('clé `fiche_batterie` non servie ⇒ omission (jamais un rendement de repli)', () => {
    expect(readFicheBatterie({})).toBeNull();
    expect(batterySimParamsFromFiche(readFicheBatterie({}))).toEqual({
      ok: false, motif: MOTIF_SIMULATION_OMISE,
    });
  });

  it('la constante de repli 0,96 n’existe plus et le simulateur refuse un rendement absent', () => {
    expect('BATTERY_ONE_WAY_EFFICIENCY' in batterySim).toBe(false);
    expect(() => simulateBattery(
      { ...base, oneWayEfficiency: undefined as unknown as number })).toThrow(RangeError);
    expect(() => simulateBattery({ ...base, oneWayEfficiency: NaN })).toThrow(RangeError);
  });
});

describe('ACAL173 — lecture du contrat ACAL10', () => {
  it('l’exemple « fiche complète » du contrat donne une simulation', () => {
    const fiche = readFicheBatterie({
      fiche_batterie: CONTRAT.exemple_autonomie_atteignable.fiche_batterie,
    });
    expect(fiche?.source).toBe('fiche');
    const params = batterySimParamsFromFiche(fiche);
    expect(params.ok).toBe(true);
  });

  it('valeurs hors bornes ⇒ jamais un rendement (null, donc omission)', () => {
    for (const aberrant of [0, -5, 140, 'x', Number.NaN]) {
      const fiche = readFicheBatterie({
        fiche_batterie: {
          rendement_ar_pct: aberrant, dod_pct: 90, source: 'fiche',
          simulation_omise_motif: null,
        },
      });
      expect(fiche?.rendementArPct).toBeNull();
      expect(fiche?.source).toBeNull();
      expect(batterySimParamsFromFiche(fiche).ok).toBe(false);
    }
  });
});
