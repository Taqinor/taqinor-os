// L-WEBT TASK2 — « Une journée type » : lib/jourTypeData.ts ships DELIBERATELY
// empty (all four months `null`) because this apps/web-only lane has no
// access to the real engine (apps.ventes.etude_horaire.jours_types_annee).
// These tests pin the zero-invented-number guarantee: hasJourTypeData()
// stays false on the shipped dataset, becomes true only once ALL FOUR months
// carry a valid 24-hour shape, and stays false on any partial/malformed set
// — the mon-toit.astro component reads this exact function to decide whether
// to render the graph at all (never a curve drawn on invented numbers).
import { afterEach, describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { JOUR_TYPE_DATA, JOUR_TYPE_MONTH_IDS, hasJourTypeData, type JourTypeMonth } from '../src/lib/jourTypeData';

// mon-toit.astro is CRLF (Windows-authored) — normalize before pinning
// multi-line source snippets so this test is line-ending-agnostic.
const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/devis/mon-toit.astro', import.meta.url)),
  'utf-8',
).replace(/\r\n/g, '\n');

function fakeMonth(): JourTypeMonth {
  return {
    prodKw: Array.from({ length: 24 }, (_, i) => (i >= 6 && i <= 18 ? 2 : 0)),
    consoKw: Array.from({ length: 24 }, () => 0.5),
    consoJourKwh: 12,
    prodJourKwh: 26,
    autoconsommeKwh: 10,
    surplusKwh: 16,
  };
}

// Snapshot to restore the shipped (empty) state after each test — the export
// is a `const` binding but the object it points to is mutable, exactly like
// the module intends for a future backend hand-off.
const ORIGINAL = { ...JOUR_TYPE_DATA };

afterEach(() => {
  for (const m of JOUR_TYPE_MONTH_IDS) JOUR_TYPE_DATA[m] = ORIGINAL[m];
});

describe('hasJourTypeData — zero-invented-number guarantee', () => {
  it('is false on the shipped dataset (all four months null)', () => {
    for (const m of JOUR_TYPE_MONTH_IDS) expect(JOUR_TYPE_DATA[m]).toBeNull();
    expect(hasJourTypeData()).toBe(false);
  });

  it('becomes true once all four months carry a valid 24-hour shape', () => {
    for (const m of JOUR_TYPE_MONTH_IDS) JOUR_TYPE_DATA[m] = fakeMonth();
    expect(hasJourTypeData()).toBe(true);
  });

  it('stays false when only some months are filled (no half-rendered comparison grid)', () => {
    JOUR_TYPE_DATA[1] = fakeMonth();
    JOUR_TYPE_DATA[4] = fakeMonth();
    // 7 and 11 stay null
    expect(hasJourTypeData()).toBe(false);
  });

  it('stays false when a shape is malformed (wrong length, negative, or non-finite)', () => {
    for (const m of JOUR_TYPE_MONTH_IDS) JOUR_TYPE_DATA[m] = fakeMonth();
    JOUR_TYPE_DATA[7]!.prodKw = JOUR_TYPE_DATA[7]!.prodKw.slice(0, 23); // 23 values, not 24
    expect(hasJourTypeData()).toBe(false);

    JOUR_TYPE_DATA[7] = fakeMonth();
    JOUR_TYPE_DATA[7]!.consoKw[0] = -1;
    expect(hasJourTypeData()).toBe(false);

    JOUR_TYPE_DATA[7] = fakeMonth();
    JOUR_TYPE_DATA[7]!.consoKw[0] = Number.NaN;
    expect(hasJourTypeData()).toBe(false);
  });
});

describe('mon-toit.astro — the graph section hides itself when data is absent (source pin)', () => {
  it('renderJourType() hides #mt-jourtype-wrap whenever hasJourTypeData() is false', () => {
    expect(PAGE).toContain("if (!hasJourTypeData()) {\n      wrap.hidden = true;\n      return;\n    }");
  });

  it('the validated colors (production gold, consumption blue dashed) are exactly as specified', () => {
    expect(PAGE).toContain("fill=\"rgba(237,161,0,0.18)\"");
    expect(PAGE).toContain('stroke="#eda100"');
    expect(PAGE).toContain('stroke="#2a78d6" stroke-width="2" stroke-dasharray="6,3"');
  });

  it('the section is hidden by default in markup (never a flash of an empty chart)', () => {
    expect(PAGE).toContain('<div id="mt-jourtype-wrap" hidden class="mt-doc-section">');
  });
});
