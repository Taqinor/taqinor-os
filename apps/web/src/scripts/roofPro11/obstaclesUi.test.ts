// @vitest-environment jsdom
// CALX91 — GESTES SUR LES SOMMETS D'UN CONTOUR FERMÉ. La géométrie (projeté orthogonal,
// refus de suppression) est prouvée dans `snap.test.ts` ; ce fichier couvre la DÉCISION que
// `obstaclesUi.ts` prend avant d'agir : Alt maintenue = suppression et JAMAIS un glissé, et
// aucun geste sommet hors des gardes déjà en place (contour fermé, hors mode obstacle /
// disposition) — donc le comportement d'aujourd'hui tant qu'Alt n'est pas maintenue.
import { describe, expect, it, vi } from 'vitest';
import {
  createObstaclesUi, // ACAL1406
  gesteSommet,
  gesteEnvironnement,
  debutGlisseEnvironnement,
  avancerGlisseEnvironnement,
  deplacementSommetAdmis, // ACAL77
  MOTIF_SOMMET_CROISE, // ACAL77
  obstacleHorsDesPans, // T4-U1-024
} from './obstaclesUi';
import {
  newEnvironmentObject,
  environmentShadeEntries,
  newLigneEnvironment, // ACAL1406
  withEnvHeight,
  withPoleDiameter,
  withCrownDiameter,
  withFutureHeight,
  withSupposeCoupe,
  withEpaisseurLigne,
} from './environment';
import { appliquerHydratationAuCtx } from './hydratation'; // ACAL1406
import { type Ctx } from './context'; // ACAL1406
import {
  aireObstacleM2,
  aireRetireeM2,
  anneauObstacle,
  champsFormeObstacle,
  clearanceForType,
  degagementObstacle,
  lireGabaritsObstacle,
  lireGabaritsZone, // ACAL1433
  motifContourObstacle,
  motifRayonObstacle,
  obstacleCercle,
  obstacleDepuisGabarit,
  obstaclePolygone,
  obstructionClearancesFor,
  type GabaritObstacle,
  type ObstacleEtendu,
} from './types';
import { bandesDepuisGabarit } from './bandeGabarit'; // ACAL1432
import {
  aireAlleeM2,
  alleeCirculation,
  couloirDepuisAxe,
  deplacerAllee,
  deserializeExclusionZones,
  empriseModuleENU,
  exclusionObstructionRings,
  exclusionZoneFromDrag,
  largeurAlleeDepuisReglages,
  poserMotifAvecLien,
  modulesSurAllee,
  motifLargeurAllee,
  serializeExclusionZones,
  type ModulePose,
} from './zones';
import { obstacleRing } from '../../lib/obstacles';
import { viderObstaclesAnnulable, questionEffacer, demanderEffacer } from './bandeauAnnuler'; // ACAL413
import { type LngLat } from '../../lib/roof';
import { lignesObjetsSite, monterObjetsSite, ouvrirObjet } from './objetsSite'; // ACAL533, ACAL1409

const ETAT = {
  sommet: 2 as number | null,
  altEnfoncee: false,
  ferme: true,
  modeObstacle: false,
  modeDisposition: false,
};

describe('CALX91 — gesteSommet : Alt maintenue supprime, jamais ne glisse', () => {
  it('sans Alt, un appui sur un sommet reste le GLISSÉ d’aujourd’hui', () => {
    expect(gesteSommet({ ...ETAT })).toBe('deplacer');
  });

  it('avec Alt, le même appui devient une SUPPRESSION', () => {
    expect(gesteSommet({ ...ETAT, altEnfoncee: true })).toBe('supprimer');
  });

  it('le sommet 0 est un sommet comme un autre (aucun index falsy oublié)', () => {
    expect(gesteSommet({ ...ETAT, sommet: 0 })).toBe('deplacer');
    expect(gesteSommet({ ...ETAT, sommet: 0, altEnfoncee: true })).toBe('supprimer');
  });
});

describe('CALX91 — gesteSommet : les gardes W92 restent intactes', () => {
  it('aucun geste hors d’un sommet', () => {
    expect(gesteSommet({ ...ETAT, sommet: null })).toBe('aucun');
    expect(gesteSommet({ ...ETAT, sommet: null, altEnfoncee: true })).toBe('aucun');
  });

  it('aucun geste tant que le contour n’est pas fermé', () => {
    expect(gesteSommet({ ...ETAT, ferme: false })).toBe('aucun');
    expect(gesteSommet({ ...ETAT, ferme: false, altEnfoncee: true })).toBe('aucun');
  });

  it('aucun geste en mode obstacle ni en mode disposition', () => {
    expect(gesteSommet({ ...ETAT, modeObstacle: true })).toBe('aucun');
    expect(gesteSommet({ ...ETAT, modeObstacle: true, altEnfoncee: true })).toBe('aucun');
    expect(gesteSommet({ ...ETAT, modeDisposition: true })).toBe('aucun');
    expect(gesteSommet({ ...ETAT, modeDisposition: true, altEnfoncee: true })).toBe('aucun');
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX105 — POSER UN ARBRE / UN BÂTIMENT AU CLIC, LE DÉPLACER AU GLISSÉ. Un objet
// atterrissait toujours 10 m au sud du centroïde ; il naît désormais SOUS LE CLIC, et se
// déplace au glissé de son marqueur. Les dimensions restent SAISIES : rien n'est déduit.
// ————————————————————————————————————————————————————————————————————————
const ETAT_ENV = {
  poseArmee: null as 'arbre' | 'batiment' | null,
  marqueur: null as string | null,
  modeObstacle: false,
  modeDisposition: false,
};

describe('CALX105 — gesteEnvironnement', () => {
  it('un mode de pose armé fait POSER au prochain clic', () => {
    expect(gesteEnvironnement({ ...ETAT_ENV, poseArmee: 'arbre' })).toBe('poser');
    expect(gesteEnvironnement({ ...ETAT_ENV, poseArmee: 'batiment' })).toBe('poser');
  });

  it('sans pose armée, un marqueur sous le doigt se DÉPLACE', () => {
    expect(gesteEnvironnement({ ...ETAT_ENV, marqueur: 'env-1' })).toBe('deplacer');
  });

  it('la pose armée l’emporte sur un marqueur sous le doigt', () => {
    expect(gesteEnvironnement({ ...ETAT_ENV, poseArmee: 'arbre', marqueur: 'env-1' })).toBe('poser');
  });

  it('rien à faire sans pose armée ni marqueur', () => {
    expect(gesteEnvironnement({ ...ETAT_ENV })).toBe('aucun');
  });

  it('les modes obstacle et disposition gardent la main (comportement inchangé)', () => {
    expect(gesteEnvironnement({ ...ETAT_ENV, poseArmee: 'arbre', modeObstacle: true })).toBe('aucun');
    expect(gesteEnvironnement({ ...ETAT_ENV, marqueur: 'env-1', modeDisposition: true })).toBe('aucun');
  });
});

describe('CALX105 — le clic donne le centre', () => {
  it('l’objet posé porte EXACTEMENT les coordonnées cliquées', () => {
    const clic: LngLat = [-7.5987, 33.4996];
    const o = newEnvironmentObject('env-1', 'arbre', clic);
    expect(o.centerLng).toBe(clic[0]);
    expect(o.centerLat).toBe(clic[1]);
  });

  it('un objet fraîchement posé ne porte AUCUNE ombre (aucune dimension déduite)', () => {
    const o = newEnvironmentObject('env-1', 'arbre', [-7.5987, 33.4996]);
    expect(o.heightM).toBeUndefined();
    expect(environmentShadeEntries([o], [-7.6, 33.5])).toEqual([]);
  });
});

describe('CALX105 — le glissé déplace le marqueur et consomme UN pas d’historique', () => {
  const objet = () => newEnvironmentObject('env-1', 'batiment', [-7.6, 33.5]);

  it('le glissé rend de NOUVELLES coordonnées (delta du pointeur)', () => {
    const o = objet();
    const glisse = debutGlisseEnvironnement(o, [-7.6, 33.5]);
    const { centre } = avancerGlisseEnvironnement(glisse, [-7.5995, 33.5004]);
    expect(centre[0]).toBeCloseTo(-7.5995, 12);
    expect(centre[1]).toBeCloseTo(33.5004, 12);
    expect(centre[0]).not.toBe(o.centerLng);
  });

  it('le point de saisie n’a pas à être le centre : c’est le DELTA qui compte', () => {
    const o = objet();
    // On saisit le marqueur légèrement à côté de son centre.
    const glisse = debutGlisseEnvironnement(o, [-7.59998, 33.50002]);
    const { centre } = avancerGlisseEnvironnement(glisse, [-7.59988, 33.50012]);
    expect(centre[0]).toBeCloseTo(o.centerLng + 0.0001, 10);
    expect(centre[1]).toBeCloseTo(o.centerLat + 0.0001, 10);
  });

  it('UN SEUL pas d’historique pour tout le glissé (CAL100)', () => {
    const glisse = debutGlisseEnvironnement(objet(), [-7.6, 33.5]);
    expect(glisse.moved).toBe(false);
    expect(avancerGlisseEnvironnement(glisse, [-7.5999, 33.5001]).pousserHistorique).toBe(true);
    expect(avancerGlisseEnvironnement(glisse, [-7.5998, 33.5002]).pousserHistorique).toBe(false);
    expect(avancerGlisseEnvironnement(glisse, [-7.5997, 33.5003]).pousserHistorique).toBe(false);
    expect(glisse.moved).toBe(true);
  });

  it('un simple tap (aucun mouvement) ne laisse rien à annuler', () => {
    const glisse = debutGlisseEnvironnement(objet(), [-7.6, 33.5]);
    expect(glisse.moved).toBe(false); // rien n'a été poussé tant qu'on n'a pas bougé
  });
});

// ACAL1406 — la liste d'environnement est montée AVANT le document : elle se relit après l'hydratation.
describe('ACAL1406 — environnement relu à la réouverture', () => {
  it('hydratation d’un document à `environment` : la liste a 3 lignes, l’ombrage est recalculé', async () => {
    document.body.innerHTML = '<div><button id="rp9-obstacle"></button></div><ul id="rp9-env-list"></ul>';
    const ctx = { obstacles: [], selectedObsId: null, obstacleMode: false, environment: [] } as unknown as Ctx;
    const map = { getSource: () => undefined, getLayer: () => undefined, getCanvas: () => ({ style: {} }), on: () => {}, dragPan: { enable() {}, disable() {} }, queryRenderedFeatures: () => [] } as never;
    const recomputeShading = vi.fn();
    const ui = createObstaclesUi(ctx, { map, recalc: () => {}, setStatus: () => {}, redrawTrace: () => {}, recomputeShading });
    expect(document.querySelectorAll('[data-env-row]')).toHaveLength(0);
    const poteau = withPoleDiameter(withEnvHeight(newEnvironmentObject('env-1', 'poteau', [-7.6, 33.4999]), 8), 0.3);
    const arbreBase = withCrownDiameter(withEnvHeight(newEnvironmentObject('env-2', 'arbre', [-7.6001, 33.4999]), 8), 4);
    const arbre = withSupposeCoupe(withFutureHeight(arbreBase, 12, 10).objet, true);
    const haie = withEpaisseurLigne(withEnvHeight(newLigneEnvironment('env-3', [[-7.6002, 33.4998], [-7.6001, 33.4998]]), 3), 0.5);
    appliquerHydratationAuCtx(ctx, { environment: [poteau, arbre, haie] });
    ui.relireEnvironment();
    expect(document.querySelectorAll('[data-env-row]')).toHaveLength(3);
    const champ = (sel: string) => document.querySelector<HTMLInputElement>(sel);
    expect(champ('[data-env-height="env-1"]')?.value).toBe('8,0');
    expect(champ('[data-env-pole="env-1"]')?.value).toBe('0,3');
    expect(champ('[data-env-crown="env-2"]')?.value).toBe('4,0');
    expect(champ('[data-env-hfut="env-2"]')?.value).toBe('12,0');
    expect(champ('[data-env-coupe="env-2"]')?.checked).toBe(true);
    expect(champ('[data-env-epaisseur="env-3"]')?.value).toBe('0,5');
    expect(recomputeShading).not.toHaveBeenCalled(); // relancé APRÈS le boot (pans du document posés)
    await Promise.resolve();
    expect(recomputeShading).toHaveBeenCalledTimes(1);
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX103 — TRACER UN OBSTACLE POLYGONAL · CALX104 — CERCLE ET GABARITS
// CALX403 — TRACER UNE ALLÉE DE CIRCULATION
//
// Repère de travail : un point de référence au Maroc, et deux conversions mètres ⇆ lng/lat
// à sa latitude — celles de la géométrie testée. Toutes les cotes des tests sont donc des
// mètres LISIBLES (une souche en L de 4 m × 4 m dont on a retiré un carré de 2 m, une allée
// de 1 m sur 10 m), et les aires attendues se vérifient à la main.
// ————————————————————————————————————————————————————————————————————————

const REF: LngLat = [-7.6, 33.5];
const TEST_DEG2M = (Math.PI / 180) * 6378137;
const TEST_COS_LAT = Math.cos((33.5 * Math.PI) / 180);
/** Point à `estM` mètres à l'est et `nordM` mètres au nord de la référence. */
const pt = (estM: number, nordM: number): LngLat => [
  REF[0] + estM / (TEST_DEG2M * TEST_COS_LAT),
  REF[1] + nordM / TEST_DEG2M,
];

/** Souche en L : un carré de 4 m × 4 m amputé du carré de 2 m de son coin nord-est.
 *  Aire 12 m², périmètre 16 m — sa boîte englobante, elle, fait 16 m². */
const CONTOUR_EN_L: LngLat[] = [pt(0, 0), pt(4, 0), pt(4, 2), pt(2, 2), pt(2, 4), pt(0, 4)];

describe('CALX103 — un obstacle polygonal se trace, et sa forme RÉELLE fait foi', () => {
  it('le contour tracé devient la forme de l’obstacle, la boîte restant le repli explicite', () => {
    const verdict = obstaclePolygone('obs-1', CONTOUR_EN_L);
    expect(verdict.ok).toBe(true);
    if (!verdict.ok) return;
    expect(verdict.obstacle.forme).toBe('polygone');
    expect(verdict.obstacle.contour).toHaveLength(6);
    // Repli explicite : la boîte englobante du L, soit 4 m × 4 m.
    expect(verdict.obstacle.lengthM).toBeCloseTo(4, 2);
    expect(verdict.obstacle.widthM).toBeCloseTo(4, 2);
    // L'anneau dessiné est le contour lui-même, pas sa boîte.
    expect(anneauObstacle(verdict.obstacle)).toHaveLength(6);
  });

  it('l’aire RETIRÉE suit le polygone dilaté du dégagement, PAS son rectangle englobant', () => {
    const verdict = obstaclePolygone('obs-1', CONTOUR_EN_L);
    expect(verdict.ok).toBe(true);
    if (!verdict.ok) return;
    const polygone = verdict.obstacle;
    // Le MÊME obstacle réduit à sa boîte englobante (ce que l'atelier faisait hier).
    const boite: ObstacleEtendu = {
      id: 'obs-boite',
      centerLng: polygone.centerLng,
      centerLat: polygone.centerLat,
      lengthM: 4,
      widthM: 4,
    };
    const d = degagementObstacle(polygone); // aucun type saisi ⇒ dégagement de base
    expect(aireObstacleM2(polygone)).toBeCloseTo(12, 1);
    expect(aireObstacleM2(boite)).toBeCloseTo(16, 1);
    // Steiner sur la forme réelle : 12 + 16·d + π·d².
    expect(aireRetireeM2(polygone)).toBeCloseTo(12 + 16 * d + Math.PI * d * d, 1);
    // …et l'encoche de 4 m² n'est PAS retirée du posable, contrairement à la boîte.
    expect(aireRetireeM2(boite) - aireRetireeM2(polygone)).toBeCloseTo(4, 1);
    expect(aireRetireeM2(polygone)).toBeLessThan(aireRetireeM2(boite));
  });

  it('un polygone CROISÉ est refusé, et le motif nomme le croisement', () => {
    const noeudPapillon: LngLat[] = [pt(0, 0), pt(4, 4), pt(4, 0), pt(0, 4)];
    const verdict = obstaclePolygone('obs-1', noeudPapillon);
    expect(verdict.ok).toBe(false);
    if (verdict.ok) return;
    expect(verdict.motif).toContain('se croise');
    expect(motifContourObstacle(noeudPapillon)).toContain('se croise');
  });

  it('moins de trois points est refusé en le disant', () => {
    const verdict = obstaclePolygone('obs-1', [pt(0, 0), pt(4, 0)]);
    expect(verdict.ok).toBe(false);
    if (verdict.ok) return;
    expect(verdict.motif).toContain('au moins trois points');
  });

  it('un obstacle SANS forme reste le rectangle d’aujourd’hui, à l’identique', () => {
    const rect = { id: 'obs-1', centerLng: REF[0], centerLat: REF[1], lengthM: 2, widthM: 3 };
    expect(anneauObstacle(rect)).toEqual(obstacleRing(rect));
    expect(champsFormeObstacle(rect)).toEqual({}); // rien d'additif n'est émis
    expect(degagementObstacle(rect)).toBe(clearanceForType(undefined));
  });

  it('la forme VOYAGE par le document (aller-retour de `champsFormeObstacle`)', () => {
    const verdict = obstaclePolygone('obs-1', CONTOUR_EN_L);
    if (!verdict.ok) throw new Error('polygone refusé');
    const emis = champsFormeObstacle(verdict.obstacle);
    expect(emis.forme).toBe('polygone');
    expect(emis.contour).toHaveLength(6);
    // Relu tel quel depuis le document (JSON pur) : identique.
    expect(champsFormeObstacle(JSON.parse(JSON.stringify(emis)))).toEqual(emis);
  });
});

describe('CALX104 — un obstacle circulaire, au rayon SAISI', () => {
  it('sans rayon saisi, la pose est refusée en nommant le champ', () => {
    const verdict = obstacleCercle('obs-1', REF, Number.NaN);
    expect(verdict.ok).toBe(false);
    if (verdict.ok) return;
    expect(verdict.motif).toContain('rayon');
    expect(motifRayonObstacle(0)).toContain('rayon');
  });

  it('avec son rayon, le disque est la forme réelle et la boîte reste son repli', () => {
    const verdict = obstacleCercle('obs-1', REF, 1.5, { type: 'cheminee' });
    expect(verdict.ok).toBe(true);
    if (!verdict.ok) return;
    expect(verdict.obstacle.forme).toBe('cercle');
    expect(verdict.obstacle.rayonM).toBe(1.5);
    expect(verdict.obstacle.lengthM).toBe(3); // carré circonscrit, 2 r
    expect(verdict.obstacle.widthM).toBe(3);
    expect(aireObstacleM2(verdict.obstacle)).toBeCloseTo(Math.PI * 1.5 * 1.5, 6);
    const d = degagementObstacle(verdict.obstacle); // cheminée : 0,50 m (PV61)
    expect(aireRetireeM2(verdict.obstacle)).toBeCloseTo(Math.PI * (1.5 + d) ** 2, 6);
  });
});

// Les réglages société utilisés par CALX104 et CALX403 — AUCUNE de ces valeurs ne vient du
// dépôt : ce sont des saisies de société, écrites ici pour le test.
const ZONES_TYPES = {
  souche: {
    libelle: 'Souche de cheminée',
    type: 'cheminee',
    longueur_m: 0.8,
    largeur_m: 0.8,
    hauteur_m: 1.2,
    retrait_m: 0.9,
    source: 'Consigne de pose de la société',
  },
  vmc_ronde: { libelle: 'VMC ronde', type: 'ventilation', rayon_m: 0.25 },
  edicule_a_mesurer: { libelle: 'Édicule à mesurer', type: 'edicule' },
};

describe('CALX104 — les gabarits d’obstacle viennent des réglages, jamais du dépôt', () => {
  it('réglages vides ⇒ AUCUN gabarit proposé (état vide, pas de cheminée « standard »)', () => {
    expect(lireGabaritsObstacle(undefined).gabarits).toEqual([]);
    expect(lireGabaritsObstacle({}).gabarits).toEqual([]);
    expect(lireGabaritsObstacle(null).refuses).toEqual([]);
  });

  it('un gabarit sans cote n’est PAS proposé, et le motif nomme les champs manquants', () => {
    const { gabarits, refuses } = lireGabaritsObstacle(ZONES_TYPES);
    expect(gabarits.map((g) => g.cle).sort()).toEqual(['souche', 'vmc_ronde']);
    expect(refuses).toHaveLength(1);
    expect(refuses[0].cle).toBe('edicule_a_mesurer');
    expect(refuses[0].motif).toContain('la longueur et la largeur');
    expect(refuses[0].motif).not.toMatch(/_m/); // ACAL1433 — aucun nom de clé interne à l'écran
  });

  it('ACAL1433 — gabarit de zone absent des refus d’obstacle ; motifs sans `longueur_m`', () => {
    const section = {
      ...ZONES_TYPES,
      bande_nord: { libelle: 'Bande coupe-feu', genre: 'bande', nature: 'INTERDITE', largeur_m: 1.2, source: 'Règle SDIS' },
      bande_sans_cote: { libelle: 'Bande sans cote', genre: 'bande', nature: 'INTERDITE' },
      rond: { libelle: 'Rond', forme: 'cercle' },
      contour: { libelle: 'Contour', forme: 'polygone', sommets: [[0, 0], [1, 0]] },
      long_seul: { libelle: 'Long seul', longueur_m: 2 },
    };
    const { gabarits, refuses } = lireGabaritsObstacle(section);
    expect(gabarits.map((g) => g.cle)).not.toContain('bande_nord');
    expect(refuses.map((r) => r.cle)).not.toContain('bande_nord');
    expect(refuses.map((r) => r.cle)).not.toContain('bande_sans_cote');
    for (const r of refuses) expect(r.motif).not.toMatch(/_m|\(sommets\)/);
    expect(refuses.find((r) => r.cle === 'long_seul')?.motif).toContain('la largeur n’est pas saisie');
    expect(lireGabaritsZone(section).gabarits.map((g) => g.cle)).toEqual(['bande_nord']);
  });

  it('ACAL1432 — gabarit bande nord 1,2 m : sommets au nord du pan, largeur 1,2 m', () => {
    const section = { bande_nord: { libelle: 'Bande coupe-feu', genre: 'bande', nature: 'INTERDITE', largeur_m: 1.2, cote: 'nord', source: 'Règle SDIS' } };
    const g = lireGabaritsZone(section).gabarits[0];
    expect(g).toMatchObject({ genre: 'bande', largeurM: 1.2, cote: 'nord' });
    const lat0 = 33.5;
    const dLat = (m: number) => m / 111319.49;
    const dLng = (m: number) => m / (111319.49 * Math.cos((lat0 * Math.PI) / 180));
    const pan: [number, number][] = [[-7.6, lat0], [-7.6 + dLng(10), lat0], [-7.6 + dLng(10), lat0 + dLat(6)], [-7.6, lat0 + dLat(6)]];
    for (const contour of [pan, [...pan].reverse()]) { // l'orientation des sommets n'y change rien
      const v = bandesDepuisGabarit(contour, g);
      if (!v.ok) throw new Error(v.motif);
      expect(v.bandes).toHaveLength(1);
      const lats = v.bandes[0].map((p) => p[1]);
      expect(Math.max(...lats)).toBeCloseTo(lat0 + dLat(6), 9); // le bord nord du pan
      expect(Math.min(...lats)).toBeCloseTo(lat0 + dLat(6 - 1.2), 9); // 1,2 m plus au sud
      const lngs = v.bandes[0].map((p) => p[0]);
      expect(Math.max(...lngs) - Math.min(...lngs)).toBeCloseTo(dLng(10), 9);
    }
  });

  it('ACAL1432 — sans côté ou sans largeur saisis, le geste dit ce qui manque ; périmètre : une bande par arête', () => {
    const pan: [number, number][] = [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001], [-7.6, 33.5001]];
    const base = { cle: 'b', libelle: 'Bande', nature: 'INTERDITE' as const, retraitM: 0, source: 's', genre: 'bande' as const };
    const sansLargeur = bandesDepuisGabarit(pan, { ...base, cote: 'nord' });
    expect(!sansLargeur.ok && sansLargeur.motif).toContain('largeur');
    const sansCote = bandesDepuisGabarit(pan, { ...base, largeurM: 1.2 });
    expect(!sansCote.ok && sansCote.motif).toContain('côté');
    const tour = bandesDepuisGabarit(pan, { ...base, largeurM: 0.5, cote: 'perimetre' });
    expect(tour.ok && tour.bandes).toHaveLength(4);
  });

  it('poser un gabarit donne un obstacle AUX COTES DU GABARIT', () => {
    const { gabarits } = lireGabaritsObstacle(ZONES_TYPES);
    const souche = gabarits.find((g) => g.cle === 'souche') as GabaritObstacle;
    const verdict = obstacleDepuisGabarit('obs-7', souche, REF);
    expect(verdict.ok).toBe(true);
    if (!verdict.ok) return;
    expect(verdict.obstacle.lengthM).toBeCloseTo(0.8, 6);
    expect(verdict.obstacle.widthM).toBeCloseTo(0.8, 6);
    expect(verdict.obstacle.heightM).toBe(1.2);
    expect(verdict.obstacle.type).toBe('cheminee');
    // Un gabarit circulaire pose un DISQUE au rayon saisi.
    const vmc = gabarits.find((g) => g.cle === 'vmc_ronde') as GabaritObstacle;
    const rond = obstacleDepuisGabarit('obs-8', vmc, REF);
    expect(rond.ok).toBe(true);
    if (!rond.ok) return;
    expect(rond.obstacle.forme).toBe('cercle');
    expect(rond.obstacle.rayonM).toBe(0.25);
  });

  it('le dégagement PROPRE d’un gabarit prime sur celui de son type, avec sa source', () => {
    const { gabarits } = lireGabaritsObstacle(ZONES_TYPES);
    const souche = gabarits.find((g) => g.cle === 'souche') as GabaritObstacle;
    const verdict = obstacleDepuisGabarit('obs-7', souche, REF);
    if (!verdict.ok) throw new Error('gabarit refusé');
    // Le type « cheminee » vaut 0,50 m (PV61) ; le gabarit, lui, porte 0,90 m.
    expect(clearanceForType('cheminee')).toBe(0.5);
    expect(degagementObstacle(verdict.obstacle)).toBe(0.9);
    expect(obstructionClearancesFor([verdict.obstacle])).toEqual([0.9]);
    expect(verdict.obstacle.sourceDegagement).toBe('Consigne de pose de la société');
    // L'aire retirée suit CE dégagement, pas celui du type.
    expect(aireRetireeM2(verdict.obstacle)).toBeCloseTo(
      0.8 * 0.8 + 3.2 * 0.9 + Math.PI * 0.81,
      1,
    );
    // Le dégagement propre et sa source VOYAGENT par le document.
    expect(champsFormeObstacle(verdict.obstacle)).toMatchObject({
      degagementM: 0.9,
      sourceDegagement: 'Consigne de pose de la société',
    });
  });

  it('un gabarit SANS dégagement propre laisse le dégagement par type inchangé', () => {
    const { gabarits } = lireGabaritsObstacle(ZONES_TYPES);
    const vmc = gabarits.find((g) => g.cle === 'vmc_ronde') as GabaritObstacle;
    const verdict = obstacleDepuisGabarit('obs-8', vmc, REF);
    if (!verdict.ok) throw new Error('gabarit refusé');
    expect(verdict.obstacle.degagementM).toBeUndefined();
    expect(degagementObstacle(verdict.obstacle)).toBe(clearanceForType('ventilation'));
  });
});

// Réglages `degagements` d'une société : UNE largeur d'allée, saisie pour le Maroc.
const DEGAGEMENTS = {
  allees_circulation: [
    { pays: 'ma', largeur_m: 1, source: 'Consigne interne', reference: 'note du 12/09' },
  ],
};

describe('CALX403 — une allée de circulation se trace, et retire sa surface', () => {
  it('une allée de 1 m sur 10 m retire 10 m² de posable', () => {
    const verdict = alleeCirculation('zone-1', [pt(0, 0), pt(10, 0)], 1, 'ma');
    expect(verdict.ok).toBe(true);
    if (!verdict.ok) return;
    expect(verdict.zone.nature).toBe('INTERDITE'); // sa surface est retirée du posable
    expect(verdict.zone.usage).toBe('circulation');
    expect(verdict.zone.axe).toHaveLength(2);
    expect(verdict.zone.largeurM).toBe(1);
    expect(aireAlleeM2(verdict.zone)).toBeCloseTo(10, 1);
    // Elle rejoint bien les obstructions du pavage (comme toute zone INTERDITE).
    expect(exclusionObstructionRings([verdict.zone])).toHaveLength(1);
  });

  it('pays sans largeur saisie ⇒ champ vide, allée refusée, réglage manquant NOMMÉ', () => {
    const lu = largeurAlleeDepuisReglages(DEGAGEMENTS, 'fr');
    expect(lu.largeurM).toBeNull(); // le champ reste vide : rien n'est supposé
    expect(lu.motif).toContain('« fr »');
    const verdict = alleeCirculation('zone-1', [pt(0, 0), pt(10, 0)], lu.largeurM, 'fr');
    expect(verdict.ok).toBe(false);
    if (verdict.ok) return;
    expect(verdict.motif).toContain('« fr »');
    expect(motifLargeurAllee(null, 'fr')).toContain('« fr »');
  });

  it('ACAL962 — le refus d’allée ne montre aucune clé brute et nomme le pays ou dit qu’il n’est pas réglé', () => {
    const phrases = [
      motifLargeurAllee(null, 'ma'),
      motifLargeurAllee(null, null),
      largeurAlleeDepuisReglages(DEGAGEMENTS, 'fr').motif,
      largeurAlleeDepuisReglages(DEGAGEMENTS, null).motif,
    ];
    for (const p of phrases) {
      expect(p).not.toContain('degagements.');
      expect(p).not.toContain('?');
    }
    expect(phrases[0]).toBe('Allée non tracée : aucune largeur d’allée n’est réglée pour le pays « ma ». Réglez-la dans Réglages › Allées.');
    expect(phrases[1]).toBe('Allée non tracée : le pays du site n’est pas réglé. Réglez-le dans Réglages simulation › Site & imagerie.');
    expect(phrases[3]).toBe(phrases[1]);
  });

  it('ACAL1737 (revue) — la phrase d’allée porte un lien vers l’ancre #site, comme l’heure légale', () => {
    const el = document.createElement('span');
    poserMotifAvecLien(el, largeurAlleeDepuisReglages(DEGAGEMENTS, null).motif);
    const a = el.querySelector('a');
    expect(a?.getAttribute('href')).toBe('/calepinage/reglages#site');
    expect(a?.textContent).toBe('Réglages simulation › Site & imagerie');
    expect(el.textContent).toBe(largeurAlleeDepuisReglages(DEGAGEMENTS, null).motif); // le texte lu ne change pas
    const sans = document.createElement('span');
    poserMotifAvecLien(sans, largeurAlleeDepuisReglages(DEGAGEMENTS, 'ma').motif);
    expect(sans.querySelector('a')).toBeNull(); // « Réglages › Allées » : pas de lien inventé
  });

  it('un pays réglé prérremplit la largeur SAISIE et CITE sa source', () => {
    const lu = largeurAlleeDepuisReglages(DEGAGEMENTS, 'ma');
    expect(lu.largeurM).toBe(1);
    expect(lu.motif).toContain('Consigne interne');
    expect(lu.motif).toContain('note du 12/09');
  });

  it('un axe d’un seul point ne fait pas une allée', () => {
    const verdict = alleeCirculation('zone-1', [pt(0, 0)], 1, 'ma');
    expect(verdict.ok).toBe(false);
    if (verdict.ok) return;
    expect(verdict.motif).toContain('au moins deux points');
  });

  it('un glissé conserve `largeurM` au millimètre et translate l’axe ET le couloir', () => {
    const verdict = alleeCirculation('zone-1', [pt(0, 0), pt(10, 0)], 1.234, 'ma');
    if (!verdict.ok) throw new Error('allée refusée');
    const avant = verdict.zone;
    const apres = deplacerAllee(avant, 0.0005, -0.0003);
    expect(apres.largeurM).toBe(1.234); // strictement la même largeur
    expect(apres.axe?.[0][0]).toBeCloseTo((avant.axe as LngLat[])[0][0] + 0.0005, 12);
    expect(apres.axe?.[0][1]).toBeCloseTo((avant.axe as LngLat[])[0][1] - 0.0003, 12);
    expect(apres.vertices[0][0]).toBeCloseTo(avant.vertices[0][0] + 0.0005, 12);
    expect(aireAlleeM2(apres)).toBeCloseTo(aireAlleeM2(avant), 3); // même couloir
  });

  it('deux modules en travers sont COMPTÉS, et AUCUN n’est retiré', () => {
    const verdict = alleeCirculation('zone-1', [pt(0, 0), pt(10, 0)], 1, 'ma');
    if (!verdict.ok) throw new Error('allée refusée');
    // Trois modules de 1,70 m (rangée) × 1,60 m (profondeur au sol) : deux posés EN TRAVERS
    // de l'allée (ils l'enjambent sans qu'aucun coin n'y tombe), un à 6 m au nord.
    const module = (repere: string, cx: number, cy: number): ModulePose => ({
      repere,
      empriseM: empriseModuleENU({ cx, cy }, 180, 1.7, 1.6),
    });
    const modules = [module('M1', 2, 0), module('M2', 5, 0), module('M3', 2, 6)];
    const touches = modulesSurAllee(modules, verdict.zone, REF);
    expect(touches.sort()).toEqual(['M1', 'M2']);
    expect(modules).toHaveLength(3); // rien n'a été supprimé : on COMPTE, on n'efface pas
  });

  it('l’allée VOYAGE par le document : usage, axe et largeur survivent à l’aller-retour', () => {
    const verdict = alleeCirculation('zone-1', [pt(0, 0), pt(6, 0), pt(6, 5)], 1.2, 'ma');
    if (!verdict.ok) throw new Error('allée refusée');
    const emis = serializeExclusionZones([verdict.zone]);
    expect(emis[0].usage).toBe('circulation');
    expect(emis[0].axe).toHaveLength(3);
    expect(emis[0].largeurM).toBe(1.2);
    const relu = deserializeExclusionZones(JSON.parse(JSON.stringify(emis)));
    expect(relu[0].usage).toBe('circulation');
    expect(relu[0].largeurM).toBe(1.2);
    expect(relu[0].axe).toHaveLength(3);
  });

  it('une zone d’exclusion ORDINAIRE ne gagne aucune clé d’allée (comportement inchangé)', () => {
    const ordinaire = exclusionZoneFromDrag('zone-9', 'INTERDITE', pt(0, 0), pt(3, 3));
    const emis = serializeExclusionZones([ordinaire]);
    expect(emis[0].usage).toBeUndefined();
    expect(emis[0].axe).toBeUndefined();
    expect(emis[0].largeurM).toBeUndefined();
    expect(modulesSurAllee([], ordinaire, REF)).toEqual([]);
    expect(deplacerAllee(ordinaire, 0.001, 0.001)).toBe(ordinaire); // inchangée
  });

  it('le couloir garde la largeur saisie au coude (décalage sur la bissectrice)', () => {
    const couloir = couloirDepuisAxe([pt(0, 0), pt(6, 0), pt(6, 6)], 1) as LngLat[];
    expect(couloir).toHaveLength(6);
    // Deux branches de 6 m à 1 m de large, coude compris : entre 11 et 12 m².
    const zone = { id: 'z', nature: 'INTERDITE' as const, vertices: couloir, setbackM: 0 };
    expect(aireAlleeM2(zone)).toBeGreaterThan(11);
    expect(aireAlleeM2(zone)).toBeLessThan(12.1);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL77 — le glissé d'un sommet de contour FERMÉ est gardé contre le croisement.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL77 — glisser un sommet vers un papillon', () => {
  const carre: LngLat[] = [[0, 0], [10, 0], [10, 10], [0, 10]];

  it('glisser un sommet vers un papillon → sommets inchangés et motif affiché', () => {
    // Le sommet 2 tiré au-delà du côté opposé (à l'ouest du côté 3→0) : nœud papillon.
    expect(deplacementSommetAdmis(carre, 2, [-5, 5])).toBe(false);
    // Un déplacement raisonnable reste admis.
    expect(deplacementSommetAdmis(carre, 2, [12, 11])).toBe(true);
    expect(MOTIF_SOMMET_CROISE).toMatch(/nœud papillon/);
  });
});

describe('ACAL413 — un filet pour les effacements de masse', () => {
  it('« Tout effacer » puis Annuler rend les obstacles (photo AVANT de vider)', () => {
    const obstacles = [1, 2, 3, 4, 5, 6];
    const piles: number[][] = [];
    const ctx = { obstacles: [...obstacles] as unknown[], pushWorkshopHistory: () => void piles.push([...(ctx.obstacles as number[])]) };
    expect(viderObstaclesAnnulable(ctx)).toBe(6);
    expect(ctx.obstacles).toEqual([]);
    // annuler = ré-appliquer la dernière photo : les 6 obstacles, identiques
    expect(piles.at(-1)).toEqual(obstacles);
  });
  it('sans obstacle : rien n’est photographié ni vidé', () => {
    const piles: number[] = [];
    const ctx = { obstacles: [] as unknown[], pushWorkshopHistory: () => void piles.push(1) };
    expect(viderObstaclesAnnulable(ctx)).toBe(0);
    expect(piles).toEqual([]);
  });
  it('« Effacer » nomme ce qui sera perdu, et ne demande rien sans rien à perdre', () => {
    expect(questionEffacer({ pans: 1, obstacles: 2, consommation: true, ombres: true })).toBe(
      'Effacer 1 pan, 2 obstacles, la consommation saisie et les ombres tracées ?',
    );
    expect(questionEffacer({ pans: 0, obstacles: 0, consommation: false, ombres: false })).toBeNull();
  });
  it('« Effacer » sans rien à perdre part aussitôt ; avec quelque chose, rien n’est effacé avant la réponse', () => {
    let n = 0;
    demanderEffacer(null, { pans: 0, obstacles: 0, consommation: false, ombres: false }, () => { n += 1; });
    expect(n).toBe(1);
    demanderEffacer(null, { pans: 1, obstacles: 3, consommation: false, ombres: false }, () => { n += 1; });
    expect(n).toBe(1);
  });
});

// ACAL1441 — la carte « Obstacle sélectionné » : le titre vient en tête, avant Provenance et Type.
describe('ACAL1441 — titre de la carte obstacle avant les menus', () => {
  it('les sélecteurs Provenance et Type se posent APRÈS la ligne de titre, dans l’ordre d’avant', () => {
    document.body.innerHTML = '<div><button id="rp9-obstacle"></button></div><div id="rp9-obs-edit"><div id="rp9-obs-titre"><span>Obstacle sélectionné</span></div><p id="rp9-obs-corps"></p></div>';
    const ctx = { obstacles: [], selectedObsId: null, obstacleMode: false, environment: [] } as unknown as Ctx;
    const map = { getSource: () => undefined, getLayer: () => undefined, getCanvas: () => ({ style: {} }), on: () => {}, dragPan: { enable() {}, disable() {} }, queryRenderedFeatures: () => [] } as never;
    createObstaclesUi(ctx, { map, recalc: () => {}, setStatus: () => {}, redrawTrace: () => {} });
    const enfants = Array.from(document.getElementById('rp9-obs-edit')!.children).map((e) => e.id || e.className);
    expect(enfants).toEqual(['rp9-obs-titre', 'rp9-obs-provenance-row', 'rp9-obs-type-row', 'rp9-obs-corps']);
  });
});

// ACAL1409 — le tableau « Objets du site » suit chaque pose d'obstacle et la réouverture (même pan).
describe('ACAL1409 — Objets du site à chaque pose et à la réouverture', () => {
  it('poser un obstacle puis hydrater : le bloc objets-site porte deux boutons `data-objet`', () => {
    document.body.innerHTML = '<div><button id="rp9-obstacle"></button></div>';
    const ctx = { obstacles: [], selectedObsId: null, obstacleMode: false, environment: [], activeAreaId: 'a1', areas: [{ id: 'a1', label: 'Pan 1', obstacles: [] }] } as unknown as Ctx;
    const map = { getSource: () => undefined, getLayer: () => undefined, getCanvas: () => ({ style: {} }), on: () => {}, dragPan: { enable() {}, disable() {} }, queryRenderedFeatures: () => [] } as never;
    const ui = createObstaclesUi(ctx, { map, recalc: () => {}, setStatus: () => {}, redrawTrace: () => {} });
    const selectionnes: string[] = [];
    const objetsSite = monterObjetsSite(ctx, { selectArea: () => {}, selectObstacle: (id) => selectionnes.push(id) });
    ui.apresRedessin(objetsSite.redessiner);
    const boutons = () => Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-objets-site [data-objet]'));
    expect(document.getElementById('rp9-objets-site')?.hidden).toBe(true);
    const cheminee = { id: 'obs-1', centerLng: -7.6, centerLat: 33.5, lengthM: 0.8, widthM: 0.8, heightM: 1.2, type: 'cheminee' };
    ui.addObstacle({ ...cheminee });
    ui.addObstacle({ ...cheminee, id: 'obs-2', centerLng: -7.5999, lengthM: 1.2, widthM: 1, heightM: 0.5, type: 'velux' });
    expect(boutons().map((b) => b.dataset.objet)).toEqual(['obs-1', 'obs-2']);
    // Réouverture : le document relu remplace les obstacles du pan, puis l'atelier les redessine.
    ctx.obstacles = JSON.parse(JSON.stringify(ctx.obstacles));
    document.getElementById('rp9-objets-site')!.innerHTML = '';
    ui.redrawObstacles();
    expect(document.getElementById('rp9-objets-site')?.hidden).toBe(false);
    expect(boutons()).toHaveLength(2);
    expect(boutons()[0].textContent).toContain('0,8 × 0,8 m · hauteur 1,2 m');
    boutons()[1].click();
    expect(selectionnes).toEqual(['obs-2']);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL533 — le tableau « Objets du site ».
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL533 — lignesObjetsSite', () => {
  const obs = (id: string, provenance?: string, type?: string) =>
    ({ id, centerLng: -7.6, centerLat: 33.5, lengthM: 2, widthM: 1.5, ...(provenance ? { provenance } : {}), ...(type ? { type } : {}) });
  // 30 obstacles sur 2 pans : tous les 5e « devinés », le reste relevé.
  const pan1 = Array.from({ length: 15 }, (_, i) => obs(`o${i}`, i % 5 === 0 ? 'DEVINE' : 'RELEVE', 'cheminee'));
  const pan2 = Array.from({ length: 15 }, (_, i) => obs(`p${i}`, i % 5 === 0 ? 'DEVINE' : 'RELEVE', 'climatiseur'));
  const ctx = {
    activeAreaId: 'a1',
    obstacles: pan1,
    areas: [
      { id: 'a1', label: 'Pan 1', obstacles: [] },
      { id: 'a2', label: 'Pan 2', obstacles: pan2 },
    ],
  } as never;

  it('30 obstacles se listent avec le nom de leur pan (son RANG, jamais un nom resté dans le document — demande croisée ACAL1430)', () => {
    const l = lignesObjetsSite(ctx);
    expect(l).toHaveLength(30);
    expect(l.filter((x) => x.pan === 'Zone 1')).toHaveLength(15);
    expect(l.filter((x) => x.pan === 'Zone 2')).toHaveLength(15);
  });

  it('les provenances non mesurées passent d’abord (pas un tri par id)', () => {
    const l = lignesObjetsSite(ctx);
    expect(l.slice(0, 6).every((x) => x.nonMesure)).toBe(true);
    expect(l.slice(6).some((x) => x.nonMesure)).toBe(false);
    expect(l[0].provenanceLabel).toBe('Deviné');
  });

  it('le filtre de provenance et le filtre de type réduisent la liste', () => {
    expect(lignesObjetsSite(ctx, { provenance: 'DEVINE' })).toHaveLength(6);
    expect(lignesObjetsSite(ctx, { type: 'climatiseur' }).every((x) => x.pan === 'Zone 2')).toBe(true);
  });

  it('un clic sur un obstacle d’un autre pan active d’abord ce pan puis sélectionne l’obstacle', () => {
    const appels: string[] = [];
    const deps = { selectArea: (id: string) => appels.push(`pan:${id}`), selectObstacle: (id: string) => appels.push(`obs:${id}`) };
    ouvrirObjet({ id: 'p3', panId: 'a2' }, 'a1', deps);
    ouvrirObjet({ id: 'o4', panId: 'a1' }, 'a1', deps);
    expect(appels).toEqual(['pan:a2', 'obs:p3', 'obs:o4']);
  });
});

/* T4-U1-024 — une cheminée posée À CÔTÉ du toit était acceptée « le calepinage l'évite », sans avertissement. */
describe('T4-U1-024 — obstacleHorsDesPans : un obstacle dont le centre n’est sur aucun pan est signalé', () => {
  const pan = { id: 'area-1', vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001], [-7.6, 33.5001]] as [number, number][] };
  const sur = { centerLng: -7.59995, centerLat: 33.50005 };
  const aCote = { centerLng: -7.5997, centerLat: 33.50005 };
  it('sur le pan : non ; à côté : oui', () => {
    expect(obstacleHorsDesPans(sur, [pan])).toBe(false);
    expect(obstacleHorsDesPans(aCote, [pan])).toBe(true);
  });
  it('un pan vide (moins de trois sommets) ne contient rien ; aucun pan tracé : rien n’est signalé (rien à éviter)', () => {
    expect(obstacleHorsDesPans(sur, [{ id: 'z', vertices: [] }])).toBe(false);
    expect(obstacleHorsDesPans(sur, [])).toBe(false);
  });
});
