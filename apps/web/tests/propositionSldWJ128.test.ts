// WJ128 — Schéma électrique (SLD) : présence conditionnelle (hasSldSvg — garde
// de rendu de la section [token].astro) + nom de fichier de téléchargement
// (sldSvgFilename). Fonctions PURES, aucun DOM : la page se contente de
// brancher `{showSld && (...)}` sur `hasSldSvg(data)` et de poser
// `data-sld-filename={sldSvgFilename(reference)}` sur le bouton de
// téléchargement (Blob + URL.createObjectURL côté client).
import { describe, expect, it } from 'vitest';
import { hasSldSvg, sldSvgFilename } from '../src/lib/proposition';

describe('WJ128 — hasSldSvg (présence conditionnelle de la section « Schéma électrique »)', () => {
  it('SVG non vide → true (la section doit s’afficher)', () => {
    expect(hasSldSvg({ sld_svg: '<svg viewBox="0 0 10 10"></svg>' })).toBe(true);
  });

  it('null → false (aucune étude électrique : rien ne change sur la page)', () => {
    expect(hasSldSvg({ sld_svg: null })).toBe(false);
  });

  it('absent (undefined) → false', () => {
    expect(hasSldSvg({})).toBe(false);
  });

  it('chaîne vide ou uniquement des espaces → false', () => {
    expect(hasSldSvg({ sld_svg: '' })).toBe(false);
    expect(hasSldSvg({ sld_svg: '   ' })).toBe(false);
  });

  it('type inattendu (jamais un throw) → false', () => {
    // @ts-expect-error — payload backend douteux, la garde doit rester défensive.
    expect(hasSldSvg({ sld_svg: 42 })).toBe(false);
  });
});

describe('WJ128 — sldSvgFilename (nom de fichier du téléchargement SVG)', () => {
  it('référence simple → schema-electrique-<réf>.svg', () => {
    expect(sldSvgFilename('DEV-2026-0042')).toBe('schema-electrique-DEV-2026-0042.svg');
  });

  it('caractères non sûrs (slash, espace) → remplacés par un tiret, jamais rejetés', () => {
    expect(sldSvgFilename('DEV-2026-0042/A')).toBe('schema-electrique-DEV-2026-0042-A.svg');
    expect(sldSvgFilename('DEV 2026 0042')).toBe('schema-electrique-DEV-2026-0042.svg');
  });

  it('référence vide, null ou undefined → repli "devis" (jamais un nom de fichier vide)', () => {
    expect(sldSvgFilename('')).toBe('schema-electrique-devis.svg');
    expect(sldSvgFilename('   ')).toBe('schema-electrique-devis.svg');
    expect(sldSvgFilename(null)).toBe('schema-electrique-devis.svg');
    expect(sldSvgFilename(undefined)).toBe('schema-electrique-devis.svg');
  });

  it('référence composée UNIQUEMENT de caractères non sûrs → repli "devis" (pas de tirets nus)', () => {
    expect(sldSvgFilename('///')).toBe('schema-electrique-devis.svg');
  });

  it('toujours une extension .svg unique, jamais dupliquée', () => {
    expect(sldSvgFilename('REF.svg')).toMatch(/^schema-electrique-REF-svg\.svg$/);
  });
});
