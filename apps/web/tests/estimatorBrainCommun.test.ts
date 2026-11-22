// ACAL929 — `departageParModule` : le module supplémentaire doit « payer » son énergie. Fichier neuf : aucun test
// n'exerce `estimatorBrainCommun` seul. Les deux configurations sont celles de T1-F1-023.
import { describe, expect, it } from 'vitest';
import { departageParModule } from '../src/lib/estimatorBrainCommun';

const EO_56 = { annualKwh: 47675, placedCount: 56 };
const SUD_48 = { annualKwh: 47002, placedCount: 48 };

describe('ACAL929 — departageParModule', () => {
  it('T1-F1-023 : 673 kWh pour 8 modules (84 par module) contre 979 de moyenne ⇒ 48 modules gagne, dans les deux sens', () => {
    expect(departageParModule(SUD_48, EO_56)).toBe(true);
    expect(departageParModule(EO_56, SUD_48)).toBe(false);
  });

  it('un module supplémentaire qui rapporte au moins la moyenne gagne ; à égalité exacte aussi', () => {
    const base = { annualKwh: 1000, placedCount: 10 }; // 100 kWh par module
    expect(departageParModule({ annualKwh: 1300, placedCount: 13 }, base)).toBe(true); // +100 par module : égalité
    expect(departageParModule({ annualKwh: 1400, placedCount: 13 }, base)).toBe(true);
    expect(departageParModule({ annualKwh: 1299, placedCount: 13 }, base)).toBe(false);
  });

  it('même nombre de modules ⇒ undefined (la suite du départage reste departageBase)', () => {
    expect(departageParModule({ annualKwh: 900, placedCount: 12 }, { annualKwh: 1200, placedCount: 12 })).toBeUndefined();
    expect(departageParModule({ annualKwh: 0, placedCount: 0 }, { annualKwh: 0, placedCount: 0 })).toBeUndefined();
  });

  it('une configuration sans module perd', () => {
    expect(departageParModule({ annualKwh: 0, placedCount: 0 }, SUD_48)).toBe(false);
    expect(departageParModule(SUD_48, { annualKwh: 0, placedCount: 0 })).toBe(true);
  });
});
