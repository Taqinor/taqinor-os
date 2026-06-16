// Garde-fous des correctifs visuels de l'estimateur 3D piloté par la facture
// (/preview/toiture-3d-pro-3) :
//   A) la photo satellite est DÉTOURÉE au tracé et posée SUR le toit, alignée au
//      pixel près — l'image est demandée par centre+zoom (étendue DÉTERMINISTE,
//      pas une bbox élargie par l'API) et les UV dérivent de la vraie position des
//      sommets dans cette étendue ; le sol satellite réel reste visible autour
//      (AUCUN tapis sombre).
//   B) la taille de chaque obstacle s'affiche SUR la boîte en 3D (sprite), et le
//      libellé de cote « en dessous » (couche symbole de la carte) a disparu.
// Vérification par le SOURCE (la carte interactive ne tourne pas hors Cloudflare).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const script = read('../src/scripts/roof-tool-pro3.ts');

describe('Fix A — photo détourée au tracé, alignée, sans débordement, sol visible', () => {
  it('la face supérieure texturée est bâtie depuis le POLYGONE tracé (ShapeGeometry), pas un rectangle', () => {
    expect(script).toContain('new THREE.ShapeGeometry(shape)');
    expect(script).toContain('applyRoofPhoto(deck, deckMat, pack.origin)');
  });

  it('l’image est demandée par CENTRE+ZOOM (étendue déterministe), jamais par bbox élargie', () => {
    expect(script).toContain('roofImageRequest(ringBBox(vertices))');
    expect(script).toContain('mapboxStaticRoofImageUrl(opts.mapboxToken, req.center, req.zoom, req.w, req.h)');
  });

  it('les UV dérivent de la VRAIE position des sommets dans l’étendue CALCULÉE de l’image', () => {
    expect(script).toContain('setDeckUVs(deck.geometry, origin, req.extent)');
    expect(script).toContain('roofVertexUV(lng, lat, extent)');
    // Le sommet ENU est reprojeté en lng/lat (vraie position géographique).
    expect(script).toMatch(/const lng = origin\[0\] \+ pos\.getX\(i\)/);
    expect(script).toMatch(/const lat = origin\[1\] \+ pos\.getY\(i\)/);
  });

  it('aucun plan rectangulaire séparé ne porte la photo (imagerie posée UNIQUEMENT sur le deck)', () => {
    const imageryUses = script.split('mapboxStaticRoofImageUrl').length - 1;
    expect(imageryUses).toBeLessThanOrEqual(2); // import + unique usage dans applyRoofPhoto
    expect(script).not.toMatch(/PlaneGeometry[\s\S]{0,200}mapboxStaticRoofImageUrl/);
  });

  it('le tapis sombre (PR #103) est SUPPRIMÉ — le sol satellite reste visible autour', () => {
    expect(script).not.toContain('apronSize');
    expect(script).not.toContain('PlaneGeometry'); // plus aucun plan plein (le tapis était le seul)
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
