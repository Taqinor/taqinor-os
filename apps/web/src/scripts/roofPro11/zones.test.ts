// CAL69 — ZONES INTERDITE / RÉSERVÉE / PRÉFÉRÉE tracées dans l'atelier. Ce fichier prouve
// la partie qui FAIT la tâche, sans DOM ni carte : les trois natures se créent et se
// rééditent, elles écrivent EXACTEMENT le contrat CAL68 (`exclusionZones` :
// id/label/nature/vertices/setbackM/heightM), elles se relisent à l'identique, et — la
// garantie centrale — INTERDITE et RESERVEE produisent une obstruction (le compte de
// modules bouge), PREFEREE n'en produit AUCUNE (le compte ne bouge jamais).
import { describe, expect, it } from 'vitest';
import {
  EXCLUSION_NATURES,
  exclusionColor,
  exclusionZoneFromDrag,
  exclusionZoneRing,
  blockingExclusionZones,
  exclusionObstructionRings,
  serializeExclusionZones,
  deserializeExclusionZones,
  withZoneNature,
  withZoneSetback,
  withZoneHeight,
  withZoneLabel,
  type ExclusionZone,
} from './zones';
import { type LngLat } from '../../lib/roof';

const A: LngLat = [-7.6, 33.5];
const B: LngLat = [-7.5995, 33.5004];

describe('CAL69 — les trois natures se tracent', () => {
  it('un glissé crée un rectangle de la nature demandée, sans rien inventer d’autre', () => {
    for (const n of EXCLUSION_NATURES) {
      const z = exclusionZoneFromDrag('z1', n.id, A, B);
      expect(z.nature).toBe(n.id);
      expect(z.vertices).toHaveLength(4);
      expect(z.setbackM).toBe(0); // retrait NON saisi ⇒ 0, jamais un repli
      expect(z.heightM).toBeUndefined(); // hauteur NON renseignée
      expect(z.label).toBeUndefined();
    }
  });

  it('le code couleur est DISTINCT du rouge des obstacles, et distinct par nature', () => {
    const couleurs = EXCLUSION_NATURES.map((n) => exclusionColor(n.id));
    expect(new Set(couleurs).size).toBe(3);
    expect(couleurs).not.toContain('#ff6b6b'); // couleur des obstacles
  });
});

describe('CAL69 — chaque zone se réédite', () => {
  const base = exclusionZoneFromDrag('z1', 'INTERDITE', A, B);

  it('nature, repère, retrait et hauteur sont modifiables', () => {
    let z = withZoneNature(base, 'RESERVEE');
    z = withZoneLabel(z, '  Réserve groupe froid  ');
    z = withZoneSetback(z, 0.5);
    z = withZoneHeight(z, 1.2);
    expect(z.nature).toBe('RESERVEE');
    expect(z.label).toBe('Réserve groupe froid');
    expect(z.setbackM).toBe(0.5);
    expect(z.heightM).toBe(1.2);
  });

  it('effacer une valeur la retire, elle ne devient jamais un nombre de repli', () => {
    let z = withZoneHeight(withZoneSetback(base, 0.5), 1.2);
    z = withZoneSetback(z, null);
    z = withZoneHeight(z, null);
    z = withZoneLabel(z, '');
    expect(z.setbackM).toBe(0);
    expect(z.heightM).toBeUndefined();
    expect(z.label).toBeUndefined();
  });
});

describe('CAL69 — LA garantie : le compte bouge pour INTERDITE/RESERVEE, jamais pour PREFEREE', () => {
  const interdite = exclusionZoneFromDrag('z1', 'INTERDITE', A, B);
  const reservee = exclusionZoneFromDrag('z2', 'RESERVEE', A, B);
  const preferee = exclusionZoneFromDrag('z3', 'PREFEREE', A, B);

  it('INTERDITE et RESERVEE retirent de la surface posable', () => {
    expect(blockingExclusionZones([interdite, reservee, preferee]).map((z) => z.id)).toEqual(['z1', 'z2']);
    expect(exclusionObstructionRings([interdite])).toHaveLength(1);
    expect(exclusionObstructionRings([reservee])).toHaveLength(1);
  });

  it('PREFEREE ne produit AUCUNE obstruction — le compte ne peut pas bouger', () => {
    expect(blockingExclusionZones([preferee])).toEqual([]);
    expect(exclusionObstructionRings([preferee])).toEqual([]);
    // Ajouter une préférée à un jeu de zones ne change pas les obstructions, à l'identique.
    expect(exclusionObstructionRings([interdite, preferee])).toEqual(exclusionObstructionRings([interdite]));
  });

  it('aucune zone / liste absente ⇒ aucune obstruction (comportement d’aujourd’hui)', () => {
    expect(exclusionObstructionRings([])).toEqual([]);
    expect(exclusionObstructionRings(null)).toEqual([]);
    expect(exclusionObstructionRings(undefined)).toEqual([]);
  });

  it('le retrait SAISI dilate l’anneau, il n’est pas ignoré', () => {
    const sans = exclusionZoneRing(interdite)!;
    const avec = exclusionZoneRing(withZoneSetback(interdite, 1))!;
    // Le sommet dilaté est strictement plus loin du centre que le sommet d'origine.
    const cx = sans.reduce((a, v) => a + v[0], 0) / sans.length;
    const cy = sans.reduce((a, v) => a + v[1], 0) / sans.length;
    const d = (v: LngLat) => Math.hypot(v[0] - cx, v[1] - cy);
    expect(d(avec[0])).toBeGreaterThan(d(sans[0]));
  });

  it('une zone de moins de 3 sommets ne se dessine pas et n’obstrue rien', () => {
    const bancale: ExclusionZone = { id: 'z9', nature: 'INTERDITE', vertices: [A], setbackM: 0 };
    expect(exclusionZoneRing(bancale)).toBeNull();
    expect(exclusionObstructionRings([bancale])).toEqual([]);
  });
});

describe('CAL69 — le document écrit EXACTEMENT le contrat CAL68 et se recharge', () => {
  it('les clés écrites sont celles du contrat, et rien d’autre', () => {
    let z = exclusionZoneFromDrag('SERVITUDE-EST', 'INTERDITE', A, B);
    z = withZoneLabel(withZoneSetback(z, 0.5), 'Servitude est');
    const [written] = serializeExclusionZones([z]);
    expect(Object.keys(written).sort()).toEqual(['heightM', 'id', 'label', 'nature', 'setbackM', 'vertices']);
    expect(written.nature).toBe('INTERDITE');
    expect(written.setbackM).toBe(0.5);
    expect(written.heightM).toBeNull(); // non renseignée ⇒ null explicite
  });

  it('aller-retour : ce qui est écrit se relit à l’identique', () => {
    const list = [
      withZoneSetback(exclusionZoneFromDrag('z1', 'INTERDITE', A, B), 0.5),
      withZoneHeight(exclusionZoneFromDrag('z2', 'RESERVEE', A, B), 1.2),
      exclusionZoneFromDrag('z3', 'PREFEREE', A, B),
    ];
    expect(deserializeExclusionZones(serializeExclusionZones(list))).toEqual(list);
  });

  it('un document douteux rend une liste vide, jamais une exception ni une zone inventée', () => {
    expect(deserializeExclusionZones(null)).toEqual([]);
    expect(deserializeExclusionZones({})).toEqual([]);
    expect(deserializeExclusionZones('nope')).toEqual([]);
    expect(deserializeExclusionZones([{ id: 'x', nature: 'INCONNUE', vertices: [A, B, A] }])).toEqual([]);
    expect(deserializeExclusionZones([{ id: 'x', nature: 'INTERDITE', vertices: [A] }])).toEqual([]);
    expect(deserializeExclusionZones([{ nature: 'INTERDITE', vertices: [A, B, A] }])).toEqual([]);
  });

  it('ENVELOPPE n’est pas une zone traçable ici (c’est le contour)', () => {
    expect(EXCLUSION_NATURES.map((n) => n.id)).toEqual(['INTERDITE', 'RESERVEE', 'PREFEREE']);
    expect(serializeExclusionZones([{ id: 'e', nature: 'ENVELOPPE', vertices: [A, B, A], setbackM: 0 } as unknown as ExclusionZone])).toEqual([]);
  });
});
