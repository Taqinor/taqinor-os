// CALX91 — GESTES SUR LES SOMMETS D'UN CONTOUR FERMÉ. La géométrie (projeté orthogonal,
// refus de suppression) est prouvée dans `snap.test.ts` ; ce fichier couvre la DÉCISION que
// `obstaclesUi.ts` prend avant d'agir : Alt maintenue = suppression et JAMAIS un glissé, et
// aucun geste sommet hors des gardes déjà en place (contour fermé, hors mode obstacle /
// disposition) — donc le comportement d'aujourd'hui tant qu'Alt n'est pas maintenue.
import { describe, expect, it } from 'vitest';
import {
  gesteSommet,
  gesteEnvironnement,
  debutGlisseEnvironnement,
  avancerGlisseEnvironnement,
} from './obstaclesUi';
import { newEnvironmentObject, environmentShadeEntries } from './environment';
import {
  aireObstacleM2,
  aireRetireeM2,
  anneauObstacle,
  champsFormeObstacle,
  clearanceForType,
  degagementObstacle,
  motifContourObstacle,
  obstaclePolygone,
  type ObstacleEtendu,
} from './types';
import { obstacleRing } from '../../lib/obstacles';
import { type LngLat } from '../../lib/roof';

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

// ————————————————————————————————————————————————————————————————————————
// CALX103 — TRACER UN OBSTACLE POLYGONAL
//
// Repère de travail : un point de référence au Maroc, et deux conversions mètres ⇆ lng/lat
// à sa latitude — celles de la géométrie testée. Toutes les cotes des tests sont donc des
// mètres LISIBLES (une souche en L de 4 m × 4 m dont on a retiré un carré de 2 m), et les
// aires attendues se vérifient à la main.
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
