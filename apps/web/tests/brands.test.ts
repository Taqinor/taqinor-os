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

  // W187 — real logos sourced where an official asset was reachable (Wikimedia
  // Commons); the rest stay null → word-mark, never a fabricated logo.
  it('W187 — every non-null logo points to a real file under public/brands/', () => {
    for (const brand of BRANDS) {
      if (brand.logo === null) continue;
      expect(brand.logo).toMatch(/^\/brands\/[a-z0-9-]+\.(svg|png)$/);
      const file = path.join(__dirname, '..', 'public', brand.logo);
      expect(readFileSync(file).byteLength).toBeGreaterThan(0);
    }
  });

  it('W187 — sourced brands have a logo; unsourced brands stay null (word-mark)', () => {
    const logoByName = Object.fromEntries(BRANDS.map((b) => [b.name, b.logo]));
    // Sourced official assets (Wikimedia SVG/PNG + Wikipedia EN + Commons BY-SA).
    expect(logoByName['Huawei']).toBe('/brands/huawei.svg');
    expect(logoByName['Nexans']).toBe('/brands/nexans.svg');
    expect(logoByName['JA Solar']).toBe('/brands/ja-solar.svg');
    expect(logoByName['Jinko']).toBe('/brands/jinko.png');
    expect(logoByName['Canadian Solar']).toBe('/brands/canadian-solar.png');
    expect(logoByName['Deye']).toBe('/brands/deye.png');
    // Dyness — no reachable official asset anywhere → honest word-mark fallback.
    expect(logoByName['Dyness']).toBeNull();
  });

  it('gives every brand a non-empty category', () => {
    for (const brand of BRANDS) {
      expect(typeof brand.category).toBe('string');
      expect(brand.category.length).toBeGreaterThan(0);
    }
  });

  // W183 — heightMultiplier is optional, but when present must be a positive number
  it('W183 — heightMultiplier, when set, is a positive number in [0.5, 2.0]', () => {
    for (const brand of BRANDS) {
      if (brand.heightMultiplier !== undefined) {
        expect(typeof brand.heightMultiplier).toBe('number');
        expect(brand.heightMultiplier).toBeGreaterThan(0.5);
        expect(brand.heightMultiplier).toBeLessThanOrEqual(2.0);
      }
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

  // W183 — grayscale/color transitions in BrandStrip
  it('W183 — applies grayscale to logos and color transition on hover', () => {
    expect(componentSrc).toContain('grayscale');
    expect(componentSrc).toContain('transition');
  });
});

describe('brands.ts integrity', () => {
  it('invents no model-number / spec strings (names + category + null logos only, plus optional optical sizing)', () => {
    // Each brand object carries name + category + logo + optional heightMultiplier.
    // No arbitrary spec strings (model numbers, wattages, etc.).
    for (const brand of BRANDS) {
      const keys = Object.keys(brand).sort();
      // Must contain exactly these core keys (heightMultiplier is optional)
      expect(keys).toContain('category');
      expect(keys).toContain('logo');
      expect(keys).toContain('name');
      // Only these known keys are permitted
      const allowedKeys = ['category', 'heightMultiplier', 'logo', 'name'];
      for (const key of keys) {
        expect(allowedKeys).toContain(key);
      }
    }
  });
});
