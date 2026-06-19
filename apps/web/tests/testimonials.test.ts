// Garde-fou d'intégrité : la preuve sociale ne ship JAMAIS de faux avis.
// La lib est livrée vide / null, et le composant garde tout rendu (markup +
// JSON-LD) derrière hasTestimonials/hasRating — donc rien ne s'affiche à vide.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { TESTIMONIALS, GOOGLE_RATING } from '../src/lib/testimonials';

const libSrc = readFileSync(
  fileURLToPath(new URL('../src/lib/testimonials.ts', import.meta.url)),
  'utf-8',
);
const componentSrc = readFileSync(
  fileURLToPath(new URL('../src/components/Testimonials.astro', import.meta.url)),
  'utf-8',
);

describe('preuve sociale — intégrité (zéro fabrication)', () => {
  it('TESTIMONIALS est livré vide (aucun faux témoignage)', () => {
    expect(Array.isArray(TESTIMONIALS)).toBe(true);
    expect(TESTIMONIALS).toHaveLength(0);
  });

  it('GOOGLE_RATING est livré null (aucune fausse note)', () => {
    expect(GOOGLE_RATING).toBeNull();
  });

  it('la lib porte un avertissement interdisant la fabrication', () => {
    expect(libSrc.toLowerCase()).toContain('jamais');
    expect(libSrc.toLowerCase()).toMatch(/invent|fabriqu/);
  });

  it('le composant garde tout markup derrière hasTestimonials/hasRating', () => {
    expect(componentSrc).toContain('hasTestimonials');
    expect(componentSrc).toContain('hasRating');
    // Rendu enveloppé dans une garde — rien ne sort à vide.
    expect(componentSrc).toContain('(hasTestimonials() || hasRating())');
  });

  it('le JSON-LD est gardé pour ne jamais être émis sur données vides', () => {
    expect(componentSrc).toContain('application/ld+json');
    // L'objet jsonLd n'est construit que si des données réelles existent.
    expect(componentSrc).toMatch(/jsonLd[\s\S]*hasTestimonials\(\) \|\| hasRating\(\)/);
    expect(componentSrc).toContain('{jsonLd &&');
  });
});
