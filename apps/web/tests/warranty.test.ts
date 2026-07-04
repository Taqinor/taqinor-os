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
