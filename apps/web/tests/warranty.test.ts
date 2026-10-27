// Garde-fou de la SOURCE UNIQUE de garantie (WB3) : warranty.ts expose les
// constantes datasheet (30 ans / ≥ 87,4 %), et l'ancien barème PERC « 84,8 % / 25 ans »
// n'apparaît plus nulle part dans src/ — SAUF les lignes de documentation de
// warranty.ts lui-même qui expliquent pourquoi ce barème est déprécié.
// Verrouille la correction WA11 (38 surfaces / 25 fichiers) : « 84,8 % » s'était
// propagé faute d'une constante unique — exactement ce que STAGES.py empêche pour
// les noms d'étape.
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import {
  PANEL_PERFORMANCE_WARRANTY_YEARS,
  PANEL_PERFORMANCE_FLOOR_PCT,
  PANEL_PRODUCT_WARRANTY_YEARS,
  BATTERY_CAPACITY_FLOOR_PCT,
  BATTERY_WARRANTY_YEARS,
  DEYE_INVERTER_WARRANTY_YEARS,
  HUAWEI_INVERTER_WARRANTY_YEARS,
} from '../src/lib/warranty';

const srcDir = fileURLToPath(new URL('../src', import.meta.url));

function walkSrc(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkSrc(p));
    else if (/\.(astro|ts|md)$/.test(e.name)) out.push(p);
  }
  return out;
}

describe('warranty.ts — source unique de garantie (WB3)', () => {
  it('expose le barème datasheet (produit 12 ans, perf. 30 ans / ≥ 87,4 %, batterie ≥ 70 %)', () => {
    expect(PANEL_PRODUCT_WARRANTY_YEARS).toBe(12);
    expect(PANEL_PERFORMANCE_WARRANTY_YEARS).toBe(30);
    expect(PANEL_PERFORMANCE_FLOOR_PCT).toBeCloseTo(87.4, 5);
    expect(BATTERY_CAPACITY_FLOOR_PCT).toBe(70);
  });

  it('aucun littéral « 84,8 » / « 84.8 » ne subsiste dans src/ (sauf la doc de warranty.ts)', () => {
    const warrantyAbs = fileURLToPath(new URL('../src/lib/warranty.ts', import.meta.url));
    const offenders: string[] = [];
    for (const abs of walkSrc(srcDir)) {
      if (abs === warrantyAbs) continue; // documentation intentionnelle du fichier lui-même
      const rel = abs.slice(srcDir.length + 1).replace(/\\/g, '/');
      readFileSync(abs, 'utf-8')
        .split('\n')
        .forEach((ln, i) => {
          if (/84[.,]8/.test(ln)) offenders.push(`${rel}:${i + 1} → ${ln.trim()}`);
        });
    }
    expect(
      offenders,
      `ancien barème PERC « 84,8 » détecté :\n${offenders.join('\n')}`,
    ).toEqual([]);
  });
});

describe('garanties onduleur / batterie — une durée, celle du Maroc (décision fondateur 27/10/2026)', () => {
  it('Deye = 5 ans, Huawei = 10 ans, Dyness = 7 ans', () => {
    expect(DEYE_INVERTER_WARRANTY_YEARS).toBe(5);
    expect(HUAWEI_INVERTER_WARRANTY_YEARS).toBe(10);
    expect(BATTERY_WARRANTY_YEARS).toBe(7);
  });

  it('aucune source (pages, fiches) n’associe Dyness à « 10 ans » / « 10 years » / « 10 سنوات » sur une même ligne', () => {
    const offenders: string[] = [];
    const re = /Dyness[^.;]{0,80}(10 ?ans|10[ -]years?|10 سنوات)|(10 ?ans|10[ -]years?|10 سنوات)[^.;]{0,80}Dyness/;
    const cibles = walkSrc(srcDir).filter((abs) => {
      const rel = abs.slice(srcDir.length + 1).replace(/\\/g, '/');
      return rel.startsWith('pages/') || rel.startsWith('content/') || rel === 'lib/fiches.ts';
    });
    for (const abs of cibles) {
      readFileSync(abs, 'utf-8')
        .split('\n')
        .forEach((ligne, i) => {
          if (re.test(ligne)) offenders.push(`${abs}:${i + 1}`);
        });
    }
    expect(offenders).toEqual([]);
  });

  it('aucune page ni fiche ne publie de fourchette ou de réserve sur ces durées', () => {
    const offenders: string[] = [];
    const interdits = [/5 à 10 ans/, /variantes? régionales?/i, /à confirmer contre le certificat/i];
    const cibles = walkSrc(srcDir).filter((abs) => {
      const rel = abs.slice(srcDir.length + 1).replace(/\\/g, '/');
      return (rel.startsWith('pages/') && !rel.startsWith('pages/proposition/')) || rel === 'lib/fiches.ts';
    });
    for (const abs of cibles) {
      const txt = readFileSync(abs, 'utf-8');
      for (const re of interdits) if (re.test(txt)) offenders.push(`${abs} → ${re}`);
    }
    expect(offenders).toEqual([]);
  });
});

describe('RWEB2 — garanties /proposition par marque posée', () => {
  it('Deye 5, Huawei 10, Dyness DL5.0C 7, Powerbox Pro 10, marque inconnue omise', async () => {
    const { garantieOnduleurAns, garantieBatterieAns } = await import('../src/lib/proposition/garanties');
    expect(garantieOnduleurAns([{ designation: 'Onduleur hybride Deye SUN-8K-SG05LP1' }])).toBe(5);
    expect(garantieOnduleurAns([{ designation: 'Onduleur réseau', marque: 'Huawei' }])).toBe(10);
    expect(garantieOnduleurAns([{ designation: 'Onduleur X' }])).toBeNull();
    expect(garantieBatterieAns([{ designation: 'Batterie Dyness DL5.0C 5,12 kWh' }])).toBe(7);
    expect(garantieBatterieAns([{ designation: 'Dyness Powerbox Pro 10.24' }])).toBe(10);
    expect(garantieBatterieAns([{ designation: 'Dyness Powerbox Pro 10.24' }, { designation: 'Dyness DL5.0C' }])).toBe(7);
    expect(garantieBatterieAns([{ designation: 'Panneau 710 Wc' }])).toBeNull();
  });

  it('RWEB19 — panneaux 12/30 ans seulement pour Canadian Solar / Jinko', async () => {
    const { garantiesPanneauxAns } = await import('../src/lib/proposition/garanties');
    expect(garantiesPanneauxAns([{ designation: 'Panneau Canadian Solar 710 Wc' }])).toEqual({ produit: 12, performance: 30 });
    expect(garantiesPanneauxAns([{ designation: 'Panneau 710 Wc', marque: 'Jinko' }])).toEqual({ produit: 12, performance: 30 });
    expect(garantiesPanneauxAns([{ designation: 'Panneau JA Solar 550 Wc' }])).toBeNull();
    expect(garantiesPanneauxAns([{ designation: 'Onduleur Deye' }])).toBeNull();
  });
});
