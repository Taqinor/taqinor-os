// Garde-fou des fiches techniques (W141–W145) : la bibliothèque /produits et
// l'alignement des slugs avec le moteur de devis Django.
import { describe, expect, it } from 'vitest';
import {
  FICHES,
  FICHE_CATEGORIES,
  fichesByCategorie,
  ficheBySlug,
  ficheDownloadHref,
} from '../src/lib/fiches';

describe('fiches techniques — manifest', () => {
  it('chaque fiche a slug unique, datasheet https et catégorie connue', () => {
    const slugs = new Set<string>();
    for (const f of FICHES) {
      expect(f.slug).toMatch(/^[a-z0-9-]+$/);
      expect(slugs.has(f.slug)).toBe(false);
      slugs.add(f.slug);
      expect(f.datasheet).toMatch(/^https:\/\//);
      expect(FICHE_CATEGORIES).toContain(f.categorie);
      expect(f.faits.length).toBeGreaterThan(0);
    }
  });

  it('le téléchargement renvoie la copie auto-hébergée si présente, sinon la source', () => {
    for (const f of FICHES) {
      expect(ficheDownloadHref(f)).toBe(f.pdf ?? f.datasheet);
    }
  });

  it('le groupement par catégorie couvre toutes les fiches', () => {
    const grouped = fichesByCategorie().flatMap((g) => g.fiches);
    expect(grouped.length).toBe(FICHES.length);
  });

  // Les slugs DOIVENT correspondre à ceux que le devis premium émet
  // (apps/ventes/quote_engine/residential/theme.py:fiche_slug) — sinon les
  // liens du PDF tombent en 404.
  it('couvre tous les slugs ciblés par les liens du devis', () => {
    for (const slug of [
      'canadian-solar-710',
      'jinko-710',
      'onduleur-huawei-reseau',
      'onduleur-deye-hybride',
      'batterie-dyness',
      'smart-meter-huawei',
      'wifi-dongle-huawei',
    ]) {
      expect(ficheBySlug(slug), `fiche manquante pour le slug ${slug}`).toBeTruthy();
    }
  });
});
