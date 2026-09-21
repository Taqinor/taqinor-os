// CALX123 — la SAISIE GÉOMÉTRIQUE d'un champ au sol dans l'atelier : le contour tracé
// devient `vertices` + `contourM` (la MÊME surface, dite deux fois), aucune valeur non
// saisie n'est écrite, et AUCUN pas inter-rangées n'est calculé côté client.
import { describe, expect, it } from 'vitest';
import {
  aireAnneauM2,
  contourMetres,
  creerChampSol,
  emettreSurfacesPose,
  lireSurfacesPose,
  modulesPoses,
  normaliserSurfacePose,
  pasInterRangeeAffiche,
  type SurfacePose,
} from './poseSurfaces';
import { geodesicAreaM2, type LngLat } from '../../lib/roof';

/** Un rectangle d'environ `largeurM` × `hauteurM` autour de Casablanca (anneau OUVERT,
 *  même convention que `ctx.vertices`). */
function rectangle(largeurM: number, hauteurM: number, lat = 33.55, lng = -7.6): LngLat[] {
  const dLat = hauteurM / 111320;
  const dLng = largeurM / (111320 * Math.cos((lat * Math.PI) / 180));
  return [
    [lng, lat],
    [lng + dLng, lat],
    [lng + dLng, lat + dLat],
    [lng, lat + dLat],
  ];
}

describe('CALX123 — le contour tracé donne vertices ET contourM, et ils disent la même surface', () => {
  it('l’aire du contour en mètres égale l’aire géodésique du tracé à 10⁻³ près', () => {
    for (const [l, h] of [[40, 25], [120, 80], [300, 220]]) {
      const anneau = rectangle(l, h);
      const contourM = contourMetres(anneau);
      expect(contourM).not.toBeNull();
      const aireM = aireAnneauM2(contourM);
      const aireGeo = geodesicAreaM2(anneau);
      expect(Math.abs(aireM - aireGeo) / aireGeo).toBeLessThan(1e-3);
    }
  });

  it('la surface écrite porte les DEUX contours, et `areaM2` est mesurée sur le tracé', () => {
    const anneau = rectangle(100, 50);
    const v = creerChampSol({ id: 'sol-1', vertices: anneau });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.surface.kind).toBe('sol');
    expect(v.surface.vertices).toHaveLength(4);
    expect(v.surface.contourM).toHaveLength(4);
    const aireContour = aireAnneauM2(v.surface.contourM);
    expect(Math.abs((v.surface.areaM2 as number) - aireContour) / aireContour).toBeLessThan(1e-3);
  });

  it('un contour de moins de trois coins est REFUSÉ en nommant le champ « contour »', () => {
    const v = creerChampSol({ id: 'sol-1', vertices: [[-7.6, 33.55], [-7.599, 33.55]] });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('contour');
    expect(v.motif).toContain('trois coins');
  });

  it('un contour sans aire (coins alignés) est REFUSÉ, jamais enregistré à moitié', () => {
    const v = creerChampSol({
      id: 'sol-1',
      vertices: [[-7.6, 33.55], [-7.599, 33.55], [-7.598, 33.55]],
    });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('contour');
  });

  it('un identifiant vide est REFUSÉ en nommant le champ « identifiant »', () => {
    const v = creerChampSol({ id: '   ', vertices: rectangle(50, 50) });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('identifiant');
  });
});

describe('CALX123 — aucune valeur de pente n’est écrite tant qu’elle n’est pas saisie', () => {
  it('sans pente saisie, `terrainSlopeDeg` est ABSENTE (jamais 0) et le manque est nommé', () => {
    const v = creerChampSol({ id: 'sol-1', vertices: rectangle(80, 60) });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect('terrainSlopeDeg' in v.surface).toBe(false);
    expect(v.surface.terrainSlopeDeg).toBeUndefined();
    expect(v.nonSaisi).toContain('pente du terrain');
  });

  it('pente saisie à 0 ⇒ écrite telle quelle (0 saisi n’est pas 0 supposé)', () => {
    const v = creerChampSol({ id: 'sol-1', vertices: rectangle(80, 60), penteTerrainDeg: 0 });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.surface.terrainSlopeDeg).toBe(0);
    expect(v.nonSaisi).not.toContain('pente du terrain');
  });

  it('azimut de rangée et inclinaison suivent la même règle, chacun nommé quand il manque', () => {
    const v = creerChampSol({ id: 'sol-1', vertices: rectangle(80, 60), azimutRangeeDeg: 180 });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.surface.rowAzimuthDeg).toBe(180);
    expect('tiltDeg' in v.surface).toBe(false);
    expect(v.nonSaisi).toContain('inclinaison des tables');
  });
});

describe('CALX123 — aucun pas inter-rangées n’est calculé dans le builder', () => {
  it('la surface écrite ne porte AUCUN plan moteur tant que le moteur n’a pas répondu', () => {
    const v = creerChampSol({ id: 'sol-1', vertices: rectangle(200, 120), inclinaisonDeg: 25 });
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(v.surface.engine).toBeUndefined();
    expect(modulesPoses(v.surface)).toBeNull();
  });

  it('le pas affiché est celui du moteur ; sans lui, la cellule reste VIDE', () => {
    const contour = rectangle(200, 120);
    const v = creerChampSol({ id: 'sol-1', vertices: contour, inclinaisonDeg: 25 });
    if (!v.ok) throw new Error('la saisie aurait dû être acceptée');
    // Plan du moteur SANS pas publié (moins de deux rangées) : rien n'est déduit.
    expect(pasInterRangeeAffiche({ ...v.surface, engine: { modules: 12 } })).toBeNull();
    // Plan du moteur AVEC pas publié : on affiche exactement ce qu'il a rendu.
    expect(pasInterRangeeAffiche({ ...v.surface, engine: { modules: 120, rowPitchM: 5.4 } })).toBe(5.4);
    // La géométrie saisie (inclinaison, aire) ne fabrique aucun pas par elle-même.
    expect(pasInterRangeeAffiche(v.surface)).toBeNull();
  });

  it('les modules posés sont ceux du moteur, jamais recomptés', () => {
    const surface: SurfacePose = {
      kind: 'sol',
      id: 'sol-1',
      areaM2: 5000,
      engine: { modules: 312, rowPitchM: 5.4 },
    };
    expect(modulesPoses(surface)).toBe(312);
    // Une surface deux fois plus grande SANS nouveau plan moteur garde le même compte.
    expect(modulesPoses({ ...surface, areaM2: 10000 })).toBe(312);
  });
});

describe('CALX123 — ce qui voyage par le document', () => {
  it('aucune surface ⇒ AUCUNE clé (le document repart inchangé)', () => {
    expect(emettreSurfacesPose([])).toEqual({});
    expect(emettreSurfacesPose(undefined)).toEqual({});
  });

  it('la clé `poseSurfaces` porte une COPIE, jamais la référence vivante de l’atelier', () => {
    const v = creerChampSol({ id: 'sol-1', vertices: rectangle(60, 40), penteTerrainDeg: 3 });
    if (!v.ok) throw new Error('la saisie aurait dû être acceptée');
    const doc = emettreSurfacesPose([v.surface]);
    expect(doc.poseSurfaces).toHaveLength(1);
    (doc.poseSurfaces as SurfacePose[])[0].vertices![0][0] = 999;
    expect(v.surface.vertices![0][0]).not.toBe(999);
  });

  it('aller-retour : ce qui est écrit se relit à l’identique', () => {
    const v = creerChampSol({
      id: 'sol-1',
      label: 'Parcelle nord',
      vertices: rectangle(150, 90),
      buildingId: 'bat-A',
      penteTerrainDeg: 4.5,
      azimutRangeeDeg: 180,
      inclinaisonDeg: 25,
    });
    if (!v.ok) throw new Error('la saisie aurait dû être acceptée');
    const relu = lireSurfacesPose(emettreSurfacesPose([v.surface]));
    expect(relu).toHaveLength(1);
    expect(relu[0]).toEqual(v.surface);
  });

  it('une entrée illisible du document est IGNORÉE, jamais « réparée »', () => {
    expect(normaliserSurfacePose({ kind: 'toit', id: 'x' })).toBeNull();
    expect(normaliserSurfacePose({ kind: 'sol', id: '  ' })).toBeNull();
    expect(lireSurfacesPose({ poseSurfaces: [{ kind: 'sol' }, null, 7] })).toEqual([]);
    expect(lireSurfacesPose({})).toEqual([]);
  });
});
