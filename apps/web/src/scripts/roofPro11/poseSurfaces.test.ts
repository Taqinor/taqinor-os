// CALX123 — la SAISIE GÉOMÉTRIQUE d'un champ au sol dans l'atelier : le contour tracé
// devient `vertices` + `contourM` (la MÊME surface, dite deux fois), aucune valeur non
// saisie n'est écrite, et AUCUN pas inter-rangées n'est calculé côté client.
import { describe, expect, it } from 'vitest';
import {
  aireAnneauM2,
  construireChampSolPose,
  construireFacadePose,
  construireMaillagesPose,
  construireOmbrierePose,
  contourMetres,
  creerChampSol,
  creerFacade,
  creerOmbriere,
  surfacePosableFacadeM2,
  emettreSurfacesPose,
  lireSurfacesPose,
  modulesPoses,
  normaliserSurfacePose,
  pasInterRangeeAffiche,
  PLAFOND_APPUIS_DESSINES,
  positionsAppuis,
  type SurfacePose,
} from './poseSurfaces';
import { geodesicAreaM2, type LngLat } from '../../lib/roof';
import { azimutNormaleArete } from './snap';
// CALX126 — la table du site vit dans `panStats.ts` ; elle est testée ici avec les
// surfaces de pose qui l'alimentent.
import { computePanStats, computeSiteStats, htmlTableSite } from './panStats';
import { type ModuleDocument } from './moduleSelect';
import { type AreaRecord } from './types';
import { type AreaResult } from '../../lib/roofAreas';

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

// ─────────────────────────────────────────────────────────────────────────────
// CALX124 — l'ombrière, poteaux compris.
// ─────────────────────────────────────────────────────────────────────────────

const ORIGINE_SCENE: LngLat = [-7.6, 33.55];

/** Une ombrière valide, avec ce que le test veut bien lui saisir. */
function ombriere(saisie: Partial<Parameters<typeof creerOmbriere>[0]> = {}) {
  const v = creerOmbriere({
    id: 'omb-1',
    vertices: rectangle(20, 10),
    inclinaisonDeg: 10,
    ...saisie,
  });
  if (!v.ok) throw new Error(`saisie refusée : ${v.motif}`);
  return v;
}

/** Un plan moteur minimal : deux tables posées dans le repère de la surface. */
const PLAN_MOTEUR = {
  modules: 24,
  rowPitchM: 4,
  tables: [
    { x0: -8, x1: -2, y0: -3, y1: 0 },
    { x0: 2, x1: 8, y0: -3, y1: 0 },
  ],
};

describe('CALX124 — sans hauteur libre saisie, la couverture reste au sol et le motif est affiché', () => {
  it('hauteur libre absente ⇒ clé absente du document et manque nommé', () => {
    const v = ombriere();
    expect('clearHeightM' in v.surface).toBe(false);
    expect(v.nonSaisi).toContain('hauteur libre');
  });

  it('hauteur libre absente ⇒ couverture posée à z = 0, et le motif est rendu', () => {
    const rendu = construireOmbrierePose(ombriere().surface, ORIGINE_SCENE, false);
    const couverture = rendu.maillages.find((m) => m.name.endsWith('-couverture'));
    expect(couverture).toBeDefined();
    expect(couverture!.position.z).toBe(0);
    expect(rendu.nonDessine.join(' ')).toContain('hauteur libre non renseignée');
    // Le placement de CAL91 le dit AUSSI, et c'est lui que l'atelier réutilise.
    expect(rendu.placement!.nonMesure.join(' ')).toContain('hauteur libre');
  });

  it('hauteur libre saisie ⇒ couverture levée à cette hauteur exacte, sans motif', () => {
    const rendu = construireOmbrierePose(
      ombriere({ hauteurLibreM: 2.8 }).surface,
      ORIGINE_SCENE,
      false,
    );
    const couverture = rendu.maillages.find((m) => m.name.endsWith('-couverture'));
    expect(couverture!.position.z).toBe(2.8);
    expect(rendu.nonDessine.join(' ')).not.toContain('hauteur libre non renseignée');
  });
});

describe('CALX124 — sans pas d’appui saisi, aucun poteau n’est rendu', () => {
  it('entraxe absent ⇒ zéro position d’appui, zéro poteau, motif nommé', () => {
    const v = ombriere({ hauteurLibreM: 2.5 });
    expect(v.surface.appuis?.pasM).toBeUndefined();
    expect(positionsAppuis(v.surface.contourM, v.surface.appuis?.pasM)).toEqual([]);
    const rendu = construireOmbrierePose(v.surface, ORIGINE_SCENE, false);
    expect(rendu.maillages.filter((m) => m.name.includes('-appui-'))).toHaveLength(0);
    expect(rendu.nonDessine.join(' ')).toContain('entraxe des appuis non renseigné');
  });

  it('entraxe saisi mais section absente ⇒ toujours aucun poteau, motif nommé', () => {
    const v = ombriere({ hauteurLibreM: 2.5, pasAppuiM: 5 });
    const rendu = construireOmbrierePose(v.surface, ORIGINE_SCENE, false);
    expect(rendu.maillages.filter((m) => m.name.includes('-appui-'))).toHaveLength(0);
    expect(rendu.nonDessine.join(' ')).toContain('section des appuis non renseignée');
  });

  it('entraxe + section + hauteur saisis ⇒ des poteaux, à l’entraxe saisi', () => {
    const v = ombriere({ hauteurLibreM: 2.5, pasAppuiM: 5, sectionAppuiM: 0.15 });
    expect(v.surface.appuis).toEqual({ pasM: 5, sectionM: 0.15 });
    const points = positionsAppuis(v.surface.contourM, 5);
    // Périmètre ≈ 2 × (20 + 10) = 60 m ⇒ ≈ 12 appuis à 5 m d'entraxe.
    expect(points.length).toBe(12);
    const rendu = construireOmbrierePose(v.surface, ORIGINE_SCENE, false);
    const poteaux = rendu.maillages.filter((m) => m.name.includes('-appui-'));
    expect(poteaux).toHaveLength(12);
    // Un poteau monte du sol à la couverture : son centre est à mi-hauteur.
    expect(poteaux[0].position.z).toBeCloseTo(1.25, 9);
  });

  it('un entraxe minuscule ne fige pas l’atelier : le plafond de dessin est DIT', () => {
    const v = ombriere({ hauteurLibreM: 2.5, pasAppuiM: 0.005, sectionAppuiM: 0.1 });
    const rendu = construireOmbrierePose(v.surface, ORIGINE_SCENE, false);
    const poteaux = rendu.maillages.filter((m) => m.name.includes('-appui-'));
    expect(poteaux.length).toBe(PLAFOND_APPUIS_DESSINES);
    expect(rendu.nonDessine.join(' ')).toContain('plafonnés');
  });
});

describe('CALX124 — l’ombre portée de l’ombrière apparaît dans la scène', () => {
  it('couverture, poteaux et tables projettent tous leur ombre', () => {
    const v = ombriere({ hauteurLibreM: 3, pasAppuiM: 6, sectionAppuiM: 0.2 });
    const surface = { ...v.surface, engine: PLAN_MOTEUR };
    const rendu = construireOmbrierePose(surface, ORIGINE_SCENE, false);
    expect(rendu.maillages.length).toBeGreaterThan(1);
    for (const m of rendu.maillages) {
      expect(m.castShadow).toBe(true);
      expect(m.receiveShadow).toBe(true);
    }
    expect(rendu.maillages.filter((m) => m.name.includes('-table-'))).toHaveLength(2);
  });

  it('les tables viennent du MOTEUR : sans plan, aucune table et le manque est dit', () => {
    const rendu = construireOmbrierePose(ombriere({ hauteurLibreM: 3 }).surface, ORIGINE_SCENE, false);
    expect(rendu.maillages.filter((m) => m.name.includes('-table-'))).toHaveLength(0);
    expect(rendu.nonDessine.join(' ')).toContain('plan du moteur non reçu');
  });

  it('les tables d’un champ au sol viennent du moteur elles aussi, et portent leur ombre', () => {
    const v = creerChampSol({ id: 'sol-1', vertices: rectangle(40, 30), inclinaisonDeg: 20 });
    if (!v.ok) throw new Error('la saisie aurait dû être acceptée');
    const rendu = construireChampSolPose(
      { ...v.surface, engine: PLAN_MOTEUR },
      ORIGINE_SCENE,
      false,
    );
    expect(rendu.maillages).toHaveLength(2);
    expect(rendu.maillages.every((m) => m.castShadow)).toBe(true);
    // Le compte de modules reste celui du moteur, jamais recompté.
    expect(rendu.placement!.modules).toBe(24);
  });

  it('aucune surface tracée ⇒ AUCUN maillage : la scène reste celle d’aujourd’hui', () => {
    expect(construireMaillagesPose([], ORIGINE_SCENE, false)).toEqual([]);
    expect(construireMaillagesPose(undefined, ORIGINE_SCENE, false)).toEqual([]);
  });
});

describe('CALX124 — aucune charge, aucune structure n’est calculée', () => {
  it('le document ne porte QUE les deux mesures d’appui du contrat', () => {
    const v = ombriere({ hauteurLibreM: 3, pasAppuiM: 6, sectionAppuiM: 0.2 });
    const doc = emettreSurfacesPose([v.surface]);
    expect(Object.keys((doc.poseSurfaces as SurfacePose[])[0].appuis!).sort()).toEqual([
      'pasM',
      'sectionM',
    ]);
  });

  it('une ombrière ne réclame ni n’écrit de pente de terrain', () => {
    const v = ombriere({ hauteurLibreM: 3 });
    expect('terrainSlopeDeg' in v.surface).toBe(false);
    expect(v.nonSaisi).not.toContain('pente du terrain');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// CALX125 — les modules en façade, sur un mur désigné du bâtiment.
// ─────────────────────────────────────────────────────────────────────────────

/** Le carré de la preuve de CALX99, tracé SO → SE → NE → NO : son côté 0 est le
 *  côté SUD, dont la normale sortante est plein sud (180°). */
function carreSOSENENO(coteM = 20, lat = 33.55, lng = -7.6): LngLat[] {
  const dLat = coteM / 111320;
  const dLng = coteM / (111320 * Math.cos((lat * Math.PI) / 180));
  return [
    [lng, lat], // SO
    [lng + dLng, lat], // SE
    [lng + dLng, lat + dLat], // NE
    [lng, lat + dLat], // NO
  ];
}

describe('CALX125 — aucune hauteur saisie ⇒ aucune surface créée, motif affiché', () => {
  it('hauteur basse absente ⇒ REFUS nommant « hauteurBasse », rien n’est créé', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(),
      areteIndex: 0,
      hauteurHauteM: 9,
    });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('hauteurBasse');
    expect(v.motif).toContain('aucune surface de façade n’est créée');
  });

  it('hauteur haute absente ⇒ REFUS nommant « hauteurHaute », jamais déduite du bâtiment', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(),
      areteIndex: 0,
      hauteurBasseM: 3,
    });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('hauteurHaute');
    expect(v.motif).toContain('jamais déduite de la hauteur du bâtiment');
  });

  it('bande sans étendue verticale (haute ≤ basse) ⇒ REFUS nommé', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(),
      areteIndex: 0,
      hauteurBasseM: 6,
      hauteurHauteM: 6,
    });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('hauteurHaute');
  });

  it('un mur qui n’existe pas sur le contour ⇒ REFUS nommant « mur »', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(),
      areteIndex: 9,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('mur');
  });
});

describe('CALX125 — l’azimut retenu est la normale sortante du mur désigné', () => {
  it('le côté SUD d’un carré tracé SO→SE→NE→NO rend 180°, et l’inclinaison 90°', () => {
    const contour = carreSOSENENO();
    const v = creerFacade({
      id: 'fac-sud',
      contourBatiment: contour,
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    });
    if (!v.ok) throw new Error(v.motif);
    expect(v.surface.kind).toBe('facade');
    expect(v.surface.rowAzimuthDeg).toBeCloseTo(azimutNormaleArete(contour[0], contour[1]), 9);
    expect(v.surface.rowAzimuthDeg).toBeCloseTo(180, 3);
    expect(v.surface.tiltDeg).toBe(90);
  });

  it('chaque côté rend SA propre normale sortante (est, nord, ouest)', () => {
    const contour = carreSOSENENO();
    const attendus = [180, 90, 0, 270];
    for (let i = 0; i < 4; i++) {
      const v = creerFacade({
        id: `fac-${i}`,
        contourBatiment: contour,
        areteIndex: i,
        hauteurBasseM: 3,
        hauteurHauteM: 9,
      });
      if (!v.ok) throw new Error(v.motif);
      expect(v.surface.rowAzimuthDeg).toBeCloseTo(attendus[i], 3);
    }
  });
});

describe('CALX125 — les modules posés suivent la surface du mur diminuée des retraits', () => {
  it('la surface posable est exactement (longueur − 2 latéraux) × (bande − haut − bas)', () => {
    expect(surfacePosableFacadeM2(20, 3, 9, {})).toBeCloseTo(20 * 6, 9);
    expect(surfacePosableFacadeM2(20, 3, 9, { lateralM: 1, basM: 0.5, hautM: 0.5 })).toBeCloseTo(
      18 * 5,
      9,
    );
    // Des retraits plus larges que le mur ⇒ AUCUNE surface (jamais ramenée à zéro).
    expect(surfacePosableFacadeM2(20, 3, 9, { lateralM: 12 })).toBeNull();
  });

  it('le contour envoyé au moteur est la bande RÉDUITE, en (le long du mur, hauteur)', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
      retraitsM: { lateralM: 1, basM: 0.5, hautM: 0.5 },
    });
    if (!v.ok) throw new Error(v.motif);
    const c = v.surface.contourM as number[][];
    expect(c[0][0]).toBeCloseTo(1, 6);
    expect(c[1][0]).toBeCloseTo(19, 3);
    expect(c[0][1]).toBeCloseTo(3.5, 9);
    expect(c[2][1]).toBeCloseTo(8.5, 9);
    expect(aireAnneauM2(c)).toBeCloseTo(v.surface.areaM2 as number, 6);
  });

  it('agrandir les retraits réduit STRICTEMENT la surface envoyée au moteur', () => {
    const base = {
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    };
    const sans = creerFacade({ id: 'a', ...base });
    const avec = creerFacade({ id: 'b', ...base, retraitsM: { lateralM: 2, basM: 1, hautM: 1 } });
    if (!sans.ok || !avec.ok) throw new Error('les deux saisies auraient dû être acceptées');
    expect(avec.surface.areaM2 as number).toBeLessThan(sans.surface.areaM2 as number);
    expect(avec.surface.areaM2).toBeCloseTo(16 * 4, 3);
  });

  it('un retrait non saisi n’est pas inventé : il vaut 0 appliqué ET il est NOMMÉ', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    });
    if (!v.ok) throw new Error(v.motif);
    expect(v.nonSaisi).toContain('retrait latéral de la façade');
    expect(v.nonSaisi).toContain('retrait bas de la façade');
    expect(v.nonSaisi).toContain('retrait haut de la façade');
  });

  it('le NOMBRE de modules reste celui du moteur : la table n’en recompte aucun', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    });
    if (!v.ok) throw new Error(v.motif);
    expect(modulesPoses(v.surface)).toBeNull();
    expect(modulesPoses({ ...v.surface, engine: { modules: 42 } })).toBe(42);
  });

  it('des retraits qui ne laissent aucune bande ⇒ REFUS nommant « retraits »', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
      retraitsM: { lateralM: 15 },
    });
    expect(v.ok).toBe(false);
    if (v.ok) return;
    expect(v.champ).toBe('retraits');
  });
});

describe('CALX125 — les modules sont rendus PLAQUÉS sur le mur, avec leur ombre', () => {
  /** Une façade sud valide, avec un plan moteur de deux modules. */
  function facadeSud() {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    });
    if (!v.ok) throw new Error(v.motif);
    return {
      ...v.surface,
      engine: {
        modules: 2,
        tables: [
          { x0: 2, x1: 4, y0: 4, y1: 5 },
          { x0: 6, x1: 8, y0: 4, y1: 5 },
        ],
      },
    };
  }

  it('la bande et chaque module portent leur ombre, à la HAUTEUR du plan moteur', () => {
    const rendu = construireFacadePose(facadeSud(), ORIGINE_SCENE, false);
    const modules = rendu.maillages.filter((m) => m.name.includes('-module-'));
    expect(rendu.maillages.some((m) => m.name.endsWith('-bande'))).toBe(true);
    expect(modules).toHaveLength(2);
    for (const m of rendu.maillages) {
      expect(m.castShadow).toBe(true);
      expect(m.receiveShadow).toBe(true);
    }
    // Le repère du mur est (le long du mur, hauteur) : un module à y = 4,5 est à 4,5 m du sol.
    expect(modules[0].position.z).toBeCloseTo(4.5, 6);
    expect(modules[1].position.z).toBeCloseTo(4.5, 6);
    // Et il est PLAQUÉ : le mur sud est à la latitude de l'origine, donc y ≈ 0.
    expect(Math.abs(modules[0].position.y)).toBeLessThan(0.1);
    expect(Math.abs(modules[1].position.y)).toBeLessThan(0.1);
    // Les deux modules sont bien décalés LE LONG du mur (x0 = 3 m puis 7 m).
    expect(modules[1].position.x - modules[0].position.x).toBeCloseTo(4, 3);
  });

  it('sans plan moteur, la bande est dessinée mais AUCUN module, et le manque est dit', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    });
    if (!v.ok) throw new Error(v.motif);
    const rendu = construireFacadePose(v.surface, ORIGINE_SCENE, false);
    expect(rendu.maillages.filter((m) => m.name.includes('-module-'))).toHaveLength(0);
    expect(rendu.nonDessine.join(' ')).toContain('plan du moteur non reçu');
  });

  it('une façade voyage par le document avec SES deux hauteurs obligatoires', () => {
    const v = creerFacade({
      id: 'fac-1',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
      buildingId: 'bat-A',
    });
    if (!v.ok) throw new Error(v.motif);
    const relu = lireSurfacesPose(emettreSurfacesPose([v.surface]));
    expect(relu).toHaveLength(1);
    expect(relu[0].kind).toBe('facade');
    expect(relu[0].hauteurBasseM).toBe(3);
    expect(relu[0].hauteurHauteM).toBe(9);
    expect(relu[0].buildingId).toBe('bat-A');
    expect(relu[0]).toEqual(v.surface);
  });

  it('`construireMaillagesPose` rend les trois genres ensemble', () => {
    const sol = creerChampSol({ id: 's', vertices: rectangle(30, 20), inclinaisonDeg: 20 });
    const omb = ombriere({ hauteurLibreM: 3 });
    const fac = creerFacade({
      id: 'f',
      contourBatiment: carreSOSENENO(20),
      areteIndex: 0,
      hauteurBasseM: 3,
      hauteurHauteM: 9,
    });
    if (!sol.ok || !fac.ok) throw new Error('les saisies auraient dû être acceptées');
    const maillages = construireMaillagesPose(
      [{ ...sol.surface, engine: PLAN_MOTEUR }, omb.surface, fac.surface],
      ORIGINE_SCENE,
      false,
    );
    expect(maillages.some((m) => m.name.startsWith('rp11-sol-'))).toBe(true);
    expect(maillages.some((m) => m.name.startsWith('rp11-ombriere-'))).toBe(true);
    expect(maillages.some((m) => m.name.startsWith('rp11-facade-'))).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// CALX126 — totaliser le site par bâtiment ET par surface de pose.
// (Le code de la table vit dans `panStats.ts` ; il est testé ici, avec les
//  surfaces de pose qui l'alimentent, plutôt que dans le test partagé de CAL84.)
// ─────────────────────────────────────────────────────────────────────────────

const CONTOUR_PAN: LngLat[] = rectangle(30, 20, 33.59, -7.6);

/** Un pan de toit rattaché à un bâtiment (CAL59). */
function pan(id: string, buildingId: string | null): AreaRecord {
  return {
    id,
    label: `Pan ${id}`,
    vertices: CONTOUR_PAN.map(([lng, lat]) => [lng, lat] as LngLat),
    obstacles: [],
    roofType: 'pitched',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    result: null,
    renderPlan: null,
    ...(buildingId ? { buildingId } : {}),
  } as AreaRecord;
}

const RESULTAT_PAN: AreaResult = {
  panels: 10,
  kwc: 5.5,
  annualKwh: 9000,
  savingsLow: 800,
  savingsHigh: 1200,
};

/** Un module de catalogue avec sa puissance SAISIE. */
const MODULE_550: ModuleDocument = {
  id: 'produit-1',
  produitId: 1,
  libelle: 'Module 550 Wc',
  longueurMm: 2278,
  largeurMm: 1134,
  epaisseurMm: 35,
  poidsKg: 28,
  pmaxWc: 550,
  source: 'fiche produit',
};

describe('CALX126 — deux bâtiments et une ombrière rendent trois lignes et deux totaux', () => {
  const pans = computePanStats([pan('a', 'bat-A'), pan('b', 'bat-B')], () => RESULTAT_PAN);
  const ombriereBatA = {
    kind: 'ombriere',
    id: 'omb-1',
    label: 'Ombrière parking',
    buildingId: 'bat-A',
    areaM2: 200,
    engine: { modules: 60 },
  };

  it('trois lignes (deux pans + une ombrière) et deux totaux de bâtiment', () => {
    const stats = computeSiteStats(pans, [ombriereBatA]);
    expect(stats.lignes).toHaveLength(3);
    expect(stats.lignes.map((l) => l.genre)).toEqual(['pan', 'pan', 'ombriere']);
    expect(stats.parBatiment).toHaveLength(2);
    expect(stats.parBatiment.map((t) => t.buildingId)).toEqual(['bat-A', 'bat-B']);
  });

  it('le total d’un bâtiment est la somme de SES lignes, pas une de plus', () => {
    const stats = computeSiteStats(pans, [ombriereBatA], () => MODULE_550);
    const batA = stats.parBatiment.find((t) => t.buildingId === 'bat-A')!;
    const batB = stats.parBatiment.find((t) => t.buildingId === 'bat-B')!;
    expect(batA.modules).toBe(10 + 60);
    expect(batB.modules).toBe(10);
    expect(stats.site.modules).toBe(80);
    expect(batA.motif).toBe('');
  });

  it('la table rendue porte trois lignes et deux totaux', () => {
    const html = htmlTableSite(computeSiteStats(pans, [ombriereBatA], () => MODULE_550));
    expect(html.match(/data-site-ligne="/g)).toHaveLength(3);
    expect(html.match(/data-site-total="/g)).toHaveLength(2);
    expect(html).toContain('Ombrière parking');
  });
});

describe('CALX126 — une surface sans plan moteur affiche des cellules vides et le DIT', () => {
  const pans = computePanStats([pan('a', 'bat-A')], () => RESULTAT_PAN);
  const solSansPlan = { kind: 'sol', id: 'sol-1', label: 'Parcelle', buildingId: 'bat-A', areaM2: 4000 };

  it('modules et kWc restent `null` — jamais 0 — et le motif nomme ce qui manque', () => {
    const ligne = computeSiteStats(pans, [solSansPlan]).lignes.find((l) => l.id === 'sol-1')!;
    expect(ligne.modules).toBeNull();
    expect(ligne.kwc).toBeNull();
    expect(ligne.areaM2).toBe(4000);
    expect(ligne.motif).toContain('plan du moteur non reçu');
  });

  it('la cellule rendue est VIDE, pas un zéro, et le total se dit PARTIEL', () => {
    const stats = computeSiteStats(pans, [solSansPlan]);
    const html = htmlTableSite(stats);
    expect(html).toContain('data-cellule-vide');
    expect(stats.parBatiment[0].motif).toContain('sans plan du moteur');
    // Le total garde ce qui est connu (le pan) sans compter la surface inconnue pour 0.
    expect(stats.parBatiment[0].modules).toBe(10);
  });

  it('un plan moteur SANS puissance de module ⇒ modules affichés, kWc vide et nommé', () => {
    const sansWatt: ModuleDocument = { ...MODULE_550, pmaxWc: null };
    const ligne = computeSiteStats(
      pans,
      [{ ...solSansPlan, engine: { modules: 120 } }],
      () => sansWatt,
    ).lignes.find((l) => l.id === 'sol-1')!;
    expect(ligne.modules).toBe(120);
    expect(ligne.kwc).toBeNull();
    expect(ligne.motif).toContain('puissance du module non renseignée');
  });

  it('une surface sans contour mesuré laisse l’aire VIDE et le dit', () => {
    const ligne = computeSiteStats(pans, [
      { kind: 'facade', id: 'fac-1', buildingId: 'bat-A', engine: { modules: 8 } },
    ]).lignes.find((l) => l.id === 'fac-1')!;
    expect(ligne.areaM2).toBeNull();
    expect(ligne.motif).toContain('contour non mesuré');
  });
});

describe('CALX126 — aucune valeur n’est recalculée dans la table', () => {
  const pans = computePanStats([pan('a', 'bat-A')], () => RESULTAT_PAN);

  it('le kWc d’un pan est celui que CAL84 a déjà calculé, repris tel quel', () => {
    const stats = computeSiteStats(pans, []);
    expect(stats.lignes[0].kwc).toBe(pans.pans[0].kwc);
    expect(stats.lignes[0].modules).toBe(pans.pans[0].panels);
  });

  it('doubler l’aire d’une surface SANS nouveau plan moteur ne change aucun compte', () => {
    const base = { kind: 'sol', id: 'sol-1', buildingId: 'bat-A', areaM2: 1000, engine: { modules: 40 } };
    const a = computeSiteStats(pans, [base], () => MODULE_550);
    const b = computeSiteStats(pans, [{ ...base, areaM2: 2000 }], () => MODULE_550);
    const ligneA = a.lignes.find((l) => l.id === 'sol-1')!;
    const ligneB = b.lignes.find((l) => l.id === 'sol-1')!;
    expect(ligneB.modules).toBe(ligneA.modules);
    expect(ligneB.kwc).toBe(ligneA.kwc);
    expect(ligneB.areaM2).toBe(2000);
  });

  it('le kWc d’une surface est `modules × puissance SAISIE`, jamais une puissance supposée', () => {
    const ligne = computeSiteStats(
      pans,
      [{ kind: 'sol', id: 'sol-1', areaM2: 900, engine: { modules: 100 } }],
      () => MODULE_550,
    ).lignes.find((l) => l.id === 'sol-1')!;
    expect(ligne.kwc).toBeCloseTo(55, 9);
    // Sans résolveur de module, AUCUN kWc n'est fabriqué.
    const sansModule = computeSiteStats(pans, [
      { kind: 'sol', id: 'sol-1', areaM2: 900, engine: { modules: 100 } },
    ]).lignes.find((l) => l.id === 'sol-1')!;
    expect(sansModule.kwc).toBeNull();
  });

  it('les surfaces de pose du document alimentent la table telles qu’elles sont écrites', () => {
    const v = creerOmbriere({
      id: 'omb-1',
      vertices: rectangle(20, 10),
      hauteurLibreM: 3,
      inclinaisonDeg: 10,
    });
    if (!v.ok) throw new Error(v.motif);
    const relu = lireSurfacesPose(emettreSurfacesPose([v.surface]));
    const ligne = computeSiteStats(pans, relu).lignes.find((l) => l.id === 'omb-1')!;
    expect(ligne.genre).toBe('ombriere');
    expect(ligne.areaM2).toBeCloseTo(v.surface.areaM2 as number, 6);
    expect(ligne.modules).toBeNull();
  });
});
