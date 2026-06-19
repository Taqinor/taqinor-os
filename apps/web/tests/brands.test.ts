import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { BRANDS } from '../src/lib/brands';

const componentSrc = readFileSync(
  path.join(__dirname, '..', 'src', 'components', 'BrandStrip.astro'),
  'utf8',
);
const brandsSrc = readFileSync(
  path.join(__dirname, '..', 'src', 'lib', 'brands.ts'),
  'utf8',
);

describe('BRANDS data', () => {
  it('ships exactly the 7 founder-confirmed brands', () => {
    expect(BRANDS).toHaveLength(7);
    const names = BRANDS.map((b) => b.name);
    expect(names).toEqual([
      'Canadian Solar',
      'JA Solar',
      'Jinko',
      'Deye',
      'Huawei',
      'Dyness',
      'Nexans',
    ]);
  });

  it('includes Jinko, Huawei and Nexans', () => {
    const names = BRANDS.map((b) => b.name);
    expect(names).toContain('Jinko');
    expect(names).toContain('Huawei');
    expect(names).toContain('Nexans');
  });

  it('ships every logo as null (word-marks render, no missing-file errors)', () => {
    for (const brand of BRANDS) {
      expect(brand.logo).toBeNull();
    }
  });

  it('gives every brand a non-empty category', () => {
    for (const brand of BRANDS) {
      expect(typeof brand.category).toBe('string');
      expect(brand.category.length).toBeGreaterThan(0);
    }
  });
});

describe('BrandStrip component', () => {
  it('renders an <img branch when a logo exists', () => {
    expect(componentSrc).toContain('brand.logo ?');
    expect(componentSrc).toContain('<img');
    expect(componentSrc).toContain('src={brand.logo}');
  });

  it('falls back to a font-display word-mark when no logo', () => {
    expect(componentSrc).toContain('font-display');
    expect(componentSrc).toContain('{brand.name}');
  });
});

describe('brands.ts integrity', () => {
  it('invents no model-number / spec strings (names + category + null logos only)', () => {
    // No digits anywhere in the brand data file (no model numbers, wattages,
    // voltages, capacities or other fabricated specs).
    const dataPortion = brandsSrc.slice(brandsSrc.indexOf('export const BRANDS'));
    expect(dataPortion).not.toMatch(/\d/);

    // Each brand object carries strictly name + category + logo, nothing else.
    for (const brand of BRANDS) {
      expect(Object.keys(brand).sort()).toEqual(['category', 'logo', 'name']);
    }
  });
});
