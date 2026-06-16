// Garde-fous des deux correctifs visuels de l'estimateur 3D piloté par la facture
// (/preview/toiture-3d-pro-3) :
//   A) la photo satellite est DÉTOURÉE au tracé et posée SUR le toit, sans voisins
//      dans la scène 3D (tapis sombre qui occulte le fond satellite) ;
//   B) la taille de chaque obstacle s'affiche SUR la boîte en 3D (sprite), et le
//      libellé de cote « en dessous » (couche symbole de la carte) a disparu.
// Vérification par le SOURCE (la carte interactive ne tourne pas hors Cloudflare).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const script = read('../src/scripts/roof-tool-pro3.ts');

describe('Fix A — photo détourée au tracé, posée sur le toit, sans voisins en 3D', () => {
  it('la face supérieure texturée est bâtie depuis le POLYGONE tracé (ShapeGeometry), pas un rectangle/plan large', () => {
    // Le deck = ShapeGeometry du tracé ; la photo y est appliquée.
    expect(script).toContain('new THREE.ShapeGeometry(shape)');
    expect(script).toContain('applyRoofPhoto(deck, deckMat, ring)');
    // Aucun plan rectangulaire séparé ne porte la photo : l'imagerie n'est posée
    // QUE via applyRoofPhoto (sur le deck), jamais sur un PlaneGeometry.
    const imageryUses = script.split('mapboxStaticRoofImageUrl').length - 1;
    expect(imageryUses).toBeLessThanOrEqual(2); // l'import + l'unique usage dans applyRoofPhoto
    expect(script).not.toMatch(/PlaneGeometry[\s\S]{0,200}mapboxStaticRoofImageUrl/);
  });

  it('les UV de la photo dérivent de la position géographique des sommets sur l’étendue de l’image (bbox), pas d’un rectangle arbitraire', () => {
    expect(script).toContain('setDeckUVs(deck.geometry, ringENU)');
    expect(script).toContain('ringBBox(vertices)');
  });

  it('un tapis sombre OPAQUE occulte le fond satellite dans la scène 3D (aucun voisin/sol hors du contour)', () => {
    expect(script).toContain('PlaneGeometry(apronSize, apronSize)');
    expect(script).toMatch(/apron[\s\S]{0,400}sceneRoot\.add\(apron\)/);
    // Tapis OPAQUE (pas de transparent:true sur son matériau) → occulte réellement.
    expect(script).not.toMatch(/apronSize\)[\s\S]{0,160}transparent: true/);
  });

  it('le repli gracieux est conservé (pas de token / échec image → deck gris, aucun crash)', () => {
    expect(script).toContain('if (!opts.mapboxToken || vertices.length < 3) return;');
    expect(script).toContain('img.onerror');
  });
});

describe('Fix B — taille affichée SUR la boîte en 3D, libellé « en dessous » supprimé', () => {
  it('plus de couche symbole de cote sur la carte (le « rp3-obs-label » est retiré)', () => {
    expect(script).not.toContain("id: 'rp3-obs-label'");
  });

  it('une étiquette par boîte existe en 3D (sprite face caméra) et est posée sur le mesh d’obstacle', () => {
    expect(script).toContain('function makeDimSprite');
    expect(script).toContain('new THREE.Sprite(');
    expect(script).toContain('const label = makeDimSprite(dimsLabel(o));');
    expect(script).toContain('mesh.add(label);');
  });

  it('l’étiquette reste lisible par-dessus la 3D (sans test de profondeur) et dimensionnée en mètres', () => {
    expect(script).toMatch(/SpriteMaterial\([\s\S]{0,120}depthTest: false/);
    expect(script).toContain('sprite.scale.set(worldW');
  });

  it('le panneau d’édition (Longueur/Largeur, −/+) reste intact', () => {
    const page = read('../src/pages/preview/toiture-3d-pro-3.astro');
    expect(page).toContain('id="rp3-obs-length"');
    expect(page).toContain('id="rp3-obs-width"');
    expect(page).toContain('id="rp3-obs-minus"');
    expect(page).toContain('id="rp3-obs-plus"');
  });
});
