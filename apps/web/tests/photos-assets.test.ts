import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * Garde-fou : chaque photo déclarée dans public/photos/manifest.json
 * (sortie de scripts/process-photos.mjs) doit exister en AVIF + WebP pour
 * chacune de ses largeurs — sinon le composant Picture servirait des 404.
 */
const photosDir = path.join(__dirname, '..', 'public', 'photos');
const manifest: Record<string, { widths: number[]; ratio: number }> = JSON.parse(
  readFileSync(path.join(photosDir, 'manifest.json'), 'utf8'),
);
const files = new Set(readdirSync(photosDir));

describe('assets photos générés', () => {
  it('le manifeste contient la sélection éditoriale complète', () => {
    expect(Object.keys(manifest).length).toBeGreaterThanOrEqual(12);
  });

  for (const [name, { widths }] of Object.entries(manifest)) {
    it(`${name} : toutes les variantes AVIF/WebP existent`, () => {
      for (const w of widths) {
        expect(files.has(`${name}-${w}.avif`), `${name}-${w}.avif`).toBe(true);
        expect(files.has(`${name}-${w}.webp`), `${name}-${w}.webp`).toBe(true);
      }
    });
  }
});
