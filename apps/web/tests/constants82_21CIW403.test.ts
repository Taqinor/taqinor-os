// CIW403 — jumeau web des constantes 82-21 aligné sur D-CIQ-4 : plafond en
// vigueur, aucune déduction de frais réseau, rien valorisé en basse tension.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as constantes from '../src/lib/constants82_21';
import {
  ANRE_TARIF_HORS_POINTE,
  ANRE_TARIF_POINTE,
  MENTION_82_21,
  PLAFOND_INJECTION_PCT,
  injectionAnnuelle,
  surplusRemunere,
  tarifExcedentDhKwh,
} from '../src/lib/constants82_21';
import { estimatePro } from '../src/lib/estimatorPro';

describe('CIW403 — constantes 82-21 (D-CIQ-4)', () => {
  it('plus aucune constante FRAIS_RESEAU, ni netTarifDhKwh', () => {
    const noms = Object.keys(constantes);
    expect(noms.filter((n) => /FRAIS_RESEAU/i.test(n))).toEqual([]);
    expect(noms).not.toContain('netTarifDhKwh');
    const src = readFileSync(fileURLToPath(new URL('../src/lib/constants82_21.ts', import.meta.url)), 'utf-8')
      .split(/\r?\n/)
      .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l))
      .join('\n');
    expect(src).not.toMatch(/FRAIS_RESEAU|6\.07|6\.38/);
  });

  it('plafond en vigueur 20 %, tarifs 0,18 / 0,21 HT, mention sans « révision »', () => {
    expect(PLAFOND_INJECTION_PCT).toBe(20);
    expect(ANRE_TARIF_HORS_POINTE).toBe(0.18);
    expect(ANRE_TARIF_POINTE).toBe(0.21);
    expect(MENTION_82_21).not.toMatch(/en révision|à vérifier/i);
    expect(MENTION_82_21).toContain('MT/HT/THT');
    expect(MENTION_82_21).toContain('hors taxes');
    expect(MENTION_82_21).toContain('01/03/2026-28/02/2027');
  });

  it('en BT : 0 kWh injecté valorisé (et raccordement inconnu aussi)', () => {
    expect(injectionAnnuelle(100_000, 50_000, 'bt')).toEqual({ kwh: 0, dh: 0 });
    expect(injectionAnnuelle(100_000, 50_000, null)).toEqual({ kwh: 0, dh: 0 });
    expect(injectionAnnuelle(100_000, 50_000, undefined)).toEqual({ kwh: 0, dh: 0 });
    expect(surplusRemunere('bt')).toBe(false);
  });

  it('en MT/HT/THT : surplus plafonné à 20 % × tarif, sans aucun frais', () => {
    for (const r of ['mt', 'ht', 'tht', 'MT']) {
      const inj = injectionAnnuelle(100_000, 50_000, r);
      expect(inj.kwh).toBe(20_000);
      expect(inj.dh).toBe(Math.round(20_000 * 0.18));
    }
    expect(injectionAnnuelle(100_000, 50_000, 'mt', true).dh).toBe(Math.round(20_000 * 0.21));
    expect(tarifExcedentDhKwh(false)).toBe(0.18);
    // surplus sous le plafond : non plafonné
    expect(injectionAnnuelle(100_000, 90_000, 'mt').kwh).toBe(10_000);
  });

  it('estimatePro transmet le raccordement : BT → 0 kWh valorisé, MT → dans le plafond', () => {
    const bt = estimatePro({ monthlyMad: 80_000, raccordement: 'bt', equipes: '1x8', enableInjection: true });
    expect(bt.ok).toBe(true);
    if (bt.ok) expect(bt.injectionPotential).toEqual({ kwh: 0, dh: 0, mention: MENTION_82_21 });
    const mt = estimatePro({ monthlyMad: 80_000, raccordement: 'mt', equipes: '1x8', enableInjection: true });
    expect(mt.ok).toBe(true);
    if (mt.ok) {
      expect(mt.injectionPotential!.kwh).toBeLessThanOrEqual(Math.round(mt.prodAnnuelleKwh * 0.2) + 1);
      expect(mt.injectionPotential!.mention).toBe(MENTION_82_21);
    }
  });
});
