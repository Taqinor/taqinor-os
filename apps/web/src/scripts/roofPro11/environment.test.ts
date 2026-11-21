// CAL67 — objets d'environnement (arbres/bâtiments voisins) : géométrie PURE, testée
// hors DOM/Three. Toutes les dimensions doivent être SAISIES ; rien n'est estimé.
import { describe, expect, it } from 'vitest';
import {
  newEnvironmentObject,
  deplacerEnvironment,
  withEnvHeight,
  withCrownDiameter,
  withFootprintDims,
  withEvergreen,
  environmentRing,
  environmentShadeEntries,
  environmentFootprintHalfWidthM,
  environmentNeedsFootprint,
  ENV_MIN_HEIGHT_M,
  ENV_MAX_HEIGHT_M,
  withPoleDiameter, // ACAL500
  withEpaisseurLigne, newLigneEnvironment, // ACAL501
  withFutureHeight, withSupposeCoupe, // ACAL502
} from './environment';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { racineDepot } from './harnaisAtelier';
import { serializeEnvironment } from './prefill';

/** ACAL500/501 — l'exemple étendu du contrat (ACAL505), lu dans le dépôt. */
const EXEMPLE_ETENDU = (JSON.parse(readFileSync(join(racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
  'contract_samples', 'roof_layout_v2.schema.json'), 'utf8')) as { exemple_environnement_etendu: Array<Record<string, unknown>> })
  .exemple_environnement_etendu;

describe('ACAL502 — hauteur future et « Supposer coupé »', () => {
  const ORIGINE: [number, number] = [-7.6, 33.5];
  const arbre = () => withCrownDiameter(withEnvHeight(newEnvironmentObject('a1', 'arbre', [-7.6, 33.4998]), 6), 4);
  it('supposeCoupe : aucune entrée d’ombre ; décocher la rétablit', () => {
    expect(environmentShadeEntries([arbre()], ORIGINE)).toHaveLength(1);
    const coupe = withSupposeCoupe(arbre(), true);
    expect(coupe.supposeCoupe).toBe(true);
    expect(environmentShadeEntries([coupe], ORIGINE)).toEqual([]);
    expect(environmentShadeEntries([withSupposeCoupe(coupe, false)], ORIGINE)).toHaveLength(1);
  });
  it('« dans 10 ans : 9 m » rangé ; hauteur future sans années : refus nommé', () => {
    const r = withFutureHeight(arbre(), 9, 10);
    expect(r.motif).toBeNull();
    expect(r.objet).toMatchObject({ hauteurFutureM: 9, dansAns: 10 });
    expect(withFutureHeight(arbre(), 9, null)).toEqual({ objet: arbre(), motif: 'Dites dans combien d’années.' });
    expect(withFutureHeight(arbre(), null, 10).motif).toContain('hauteur');
    expect(withFutureHeight(r.objet, null, null).objet).toEqual(arbre());
  });
  it('l’arbre de l’exemple du contrat fait l’aller-retour (les trois clés)', () => {
    const a = EXEMPLE_ETENDU.find((o) => o.kind === 'arbre')!;
    expect(serializeEnvironment([a as never])).toEqual([a]);
  });
});

describe('ACAL501 — ligne (haie, mur)', () => {
  const ORIGINE: [number, number] = [-7.6, 33.5];
  const dLng = 20 / (111319.49 * Math.cos((33.5 * Math.PI) / 180)); // ≈ 20 m vers l'est
  const haie = (ep: number | null = 0.5) =>
    withEpaisseurLigne(withEnvHeight(newLigneEnvironment('h1', [[-7.6, 33.5001], [-7.6 + dLng, 33.5001]]), 3), ep);
  it('haie de 20 m : une entrée d’ombre, empreinte 20 × 0,5 m, hauteur 3 − toit', () => {
    const [e, ...reste] = environmentShadeEntries([haie()], ORIGINE, 1);
    expect(reste).toEqual([]);
    expect(e.effHeightM).toBe(2);
    const f = e.footprint!;
    expect(Math.hypot(f[1][0] - f[0][0], f[1][1] - f[0][1])).toBeCloseTo(20, 1);
    expect(Math.hypot(f[3][0] - f[0][0], f[3][1] - f[0][1])).toBeCloseTo(0.5, 6);
  });
  it('sans épaisseur : aucune entrée, et l’écran demande l’épaisseur', () => {
    expect(environmentShadeEntries([haie(null)], ORIGINE)).toEqual([]);
    expect(environmentNeedsFootprint(haie(null))).toBe(true);
  });
  it('une épaisseur de 0,05 m n’est pas ramenée à 0,5 m', () => {
    expect(haie(0.05).epaisseurM).toBe(0.05);
  });
  it('le centre est calculé (milieu de la trace) et fait l’aller-retour ; sans trace ni centre ⇒ écartée', () => {
    const h = haie();
    expect(h.centerLng).toBeCloseTo(-7.6 + dLng / 2, 12);
    expect(serializeEnvironment([h])).toEqual([h]);
    expect(serializeEnvironment([{ id: 'x', kind: 'ligne', heightM: 2 } as never])).toEqual([]);
  });
  it('la ligne de l’exemple du contrat fait l’aller-retour (centre calculé ajouté)', () => {
    const l = EXEMPLE_ETENDU.find((o) => o.kind === 'ligne')!;
    const [sortie] = serializeEnvironment([l as never]);
    expect(sortie).toMatchObject(l);
    expect(serializeEnvironment([sortie])).toEqual([sortie]);
    expect(environmentShadeEntries([sortie], ORIGINE)).toHaveLength(1);
  });
});

describe('ACAL500 — poteau', () => {
  const ORIGINE: [number, number] = [-7.6, 33.5];
  const poteau = () => withPoleDiameter(withEnvHeight(newEnvironmentObject('p1', 'poteau', [-7.6001, 33.5001]), 8), 0.3);
  it('diamètre 0,3 m saisi ⇒ diameterM === 0.3 (pas ramené à 0,5 par ENV_MIN_DIM_M)', () => {
    expect(poteau().diameterM).toBe(0.3);
    expect('diameterM' in withPoleDiameter(poteau(), null)).toBe(false);
  });
  it('poteau : une entrée d’ombre de demi-largeur 0,15, hauteur 8 − toit', () => {
    const [e, ...reste] = environmentShadeEntries([poteau()], ORIGINE, 3);
    expect(reste).toEqual([]);
    expect(e.halfWidthM).toBeCloseTo(0.15, 9);
    expect(e.effHeightM).toBe(5);
  });
  it('poteau sans diamètre : aucune entrée et environmentNeedsFootprint vrai (aucun repli de 1,5 m)', () => {
    const sans = withEnvHeight(newEnvironmentObject('p2', 'poteau', [-7.6001, 33.5001]), 8);
    expect(environmentShadeEntries([sans], ORIGINE)).toEqual([]);
    expect(environmentNeedsFootprint(sans)).toBe(true);
    expect(environmentFootprintHalfWidthM(sans)).toBeNull();
  });
  it('le poteau de l’exemple du contrat fait l’aller-retour serializeEnvironment', () => {
    const p = EXEMPLE_ETENDU.find((o) => o.kind === 'poteau')!;
    expect(serializeEnvironment([p as never])).toEqual([p]);
    expect(serializeEnvironment([poteau()])).toEqual([poteau()]);
  });
});

describe('CAL67 — newEnvironmentObject : rien n’est inventé à la pose', () => {
  it('un objet fraîchement posé n’a AUCUNE dimension (ni hauteur ni diamètre)', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.59]);
    expect('heightM' in o).toBe(false);
    expect('crownDiameterM' in o).toBe(false);
    expect(o.kind).toBe('arbre');
    expect(o.centerLng).toBe(-7.6);
  });
});

describe('CAL67 — mutateurs : saisie bornée, effacement sur valeur vide/aberrante', () => {
  it('withEnvHeight borne et efface proprement', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.59]);
    expect(withEnvHeight(o, 6).heightM).toBe(6);
    expect(withEnvHeight(o, 1000).heightM).toBe(ENV_MAX_HEIGHT_M);
    expect(withEnvHeight(o, 0.01).heightM).toBe(ENV_MIN_HEIGHT_M);
    const withH = withEnvHeight(o, 6);
    expect('heightM' in withEnvHeight(withH, null)).toBe(false);
    expect('heightM' in withEnvHeight(withH, 0)).toBe(false);
    expect('heightM' in withEnvHeight(withH, NaN)).toBe(false);
  });

  it('withCrownDiameter (arbre)', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.59]);
    expect(withCrownDiameter(o, 5).crownDiameterM).toBe(5);
    expect('crownDiameterM' in withCrownDiameter(withCrownDiameter(o, 5), null)).toBe(false);
  });

  it('withFootprintDims (bâtiment)', () => {
    const o = newEnvironmentObject('e1', 'batiment', [-7.6, 33.59]);
    const withDims = withFootprintDims(o, 12, 8);
    expect(withDims.lengthM).toBe(12);
    expect(withDims.widthM).toBe(8);
    const cleared = withFootprintDims(withDims, null, null);
    expect('lengthM' in cleared).toBe(false);
    expect('widthM' in cleared).toBe(false);
  });

  it('withEvergreen applique/efface le feuillage', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.59]);
    expect(withEvergreen(o, true).evergreen).toBe(true);
    expect(withEvergreen(o, false).evergreen).toBe(false);
    expect('evergreen' in withEvergreen(withEvergreen(o, true), null)).toBe(false);
  });
});

describe('CAL67 — environmentRing : rien à dessiner sans dimension', () => {
  it('un arbre sans crownDiameterM → null (jamais un cercle de taille inventée)', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.59]);
    expect(environmentRing(o)).toBeNull();
  });

  it('un arbre avec crownDiameterM → un anneau fermé de rayon exact', () => {
    const o = withCrownDiameter(newEnvironmentObject('e1', 'arbre', [-7.6, 33.59]), 4);
    const ring = environmentRing(o);
    expect(ring).not.toBeNull();
    expect(ring!.length).toBe(16);
  });

  it('un footprint explicite prime toujours', () => {
    const fp: [number, number][] = [[-7.601, 33.591], [-7.599, 33.591], [-7.599, 33.589], [-7.601, 33.589]];
    const o = { ...newEnvironmentObject('e1', 'batiment', [-7.6, 33.59]), footprint: fp };
    expect(environmentRing(o)).toEqual(fp);
  });
});

describe('CAL67 — environmentShadeEntries : sans hauteur, aucune ombre', () => {
  const origin: [number, number] = [-7.6, 33.5];

  it('un objet sans heightM est écarté (comportement identique à son absence)', () => {
    const o = withCrownDiameter(newEnvironmentObject('e1', 'arbre', [-7.6, 33.4998]), 4);
    expect(environmentShadeEntries([o], origin)).toEqual([]);
  });

  it('un objet avec heightM produit UNE obstruction ENU, position au sud dégrade le nord', () => {
    // Objet posé légèrement au SUD de l'origine (latitude plus petite).
    const o = withEnvHeight(withCrownDiameter(newEnvironmentObject('e1', 'arbre', [-7.6, 33.4998]), 4), 6);
    const entries = environmentShadeEntries([o], origin);
    expect(entries).toHaveLength(1);
    expect(entries[0].effHeightM).toBe(6);
    expect(entries[0].y).toBeLessThan(0); // au sud de l'origine → y ENU négatif
  });

  it('supprimer l’objet restaure exactement la liste précédente (aucun résidu)', () => {
    const o = withEnvHeight(withCrownDiameter(newEnvironmentObject('e1', 'arbre', [-7.6, 33.4998]), 4), 6);
    const withObj = environmentShadeEntries([o], origin);
    const withoutObj = environmentShadeEntries([], origin);
    expect(withObj).toHaveLength(1);
    expect(withoutObj).toEqual([]);
  });
});

describe('CORRECTIF — sans EMPRISE saisie, aucune ombre (jamais un repli de 1,5 m)', () => {
  const origin: [number, number] = [-7.6, 33.5];
  const south: [number, number] = [-7.6, 33.4998];
  const base = newEnvironmentObject('e4', 'batiment', south);

  it('un arbre AVEC hauteur mais SANS houppier ne produit aucune obstruction', () => {
    const o = withEnvHeight(newEnvironmentObject('e1', 'arbre', south), 6);
    expect(environmentFootprintHalfWidthM(o)).toBeNull();
    expect(environmentShadeEntries([o], origin)).toEqual([]);
    expect(environmentNeedsFootprint(o)).toBe(true);
  });

  it('un bâtiment AVEC hauteur mais SANS longueur/largeur ni emprise ne produit aucune obstruction', () => {
    const o = withEnvHeight(newEnvironmentObject('e2', 'batiment', south), 9);
    expect(environmentShadeEntries([o], origin)).toEqual([]);
    expect(environmentNeedsFootprint(o)).toBe(true);
  });

  it('dès que l’emprise est saisie, la demi-largeur vient de CETTE saisie', () => {
    const o = withEnvHeight(withCrownDiameter(newEnvironmentObject('e3', 'arbre', south), 4), 6);
    const entries = environmentShadeEntries([o], origin);
    expect(entries).toHaveLength(1);
    expect(entries[0].halfWidthM).toBeCloseTo(2, 6);
    expect(environmentNeedsFootprint(o)).toBe(false);
  });

  it('une emprise polygonale donne la demi-largeur du rayon maximal mesuré, pas un repli', () => {
    const d = 10 / 111320; // ≈ 10 m en latitude
    const o: typeof base = { ...base, heightM: 8, footprint: [
      [south[0] - d, south[1] - d],
      [south[0] + d, south[1] - d],
      [south[0] + d, south[1] + d],
      [south[0] - d, south[1] + d],
    ] };
    const entries = environmentShadeEntries([o], origin);
    expect(entries).toHaveLength(1);
    expect(entries[0].halfWidthM).toBeGreaterThan(10); // demi-diagonale ≈ 14 m, mesurée
    expect(environmentNeedsFootprint(o)).toBe(false);
  });

  it('sans hauteur, l’objet n’est pas signalé « emprise à saisir » (il est déjà sans ombre)', () => {
    const o = newEnvironmentObject('e5', 'batiment', south);
    expect(environmentNeedsFootprint(o)).toBe(false);
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX105 — POSE AU CLIC ET DÉPLACEMENT AU GLISSÉ. Un objet ne naît plus 10 m au sud du
// centroïde : il naît SOUS LE CLIC et se repose où on le glisse. Déplacer n'invente jamais
// de dimension — un objet sans hauteur saisie reste sans ombre, avant comme après.
// ————————————————————————————————————————————————————————————————————————
describe('CALX105 — deplacerEnvironment', () => {
  const origin: [number, number] = [-7.6, 33.5];

  it('repose l’objet EXACTEMENT sur le point demandé', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.49]);
    const bouge = deplacerEnvironment(o, [-7.5987, 33.4996]);
    expect(bouge.centerLng).toBe(-7.5987);
    expect(bouge.centerLat).toBe(33.4996);
  });

  it('ne touche à AUCUNE dimension saisie', () => {
    const o = withCrownDiameter(withEnvHeight(newEnvironmentObject('e1', 'arbre', [-7.6, 33.49]), 8), 5);
    const bouge = deplacerEnvironment(o, [-7.5987, 33.4996]);
    expect(bouge.heightM).toBe(o.heightM);
    expect(bouge.crownDiameterM).toBe(o.crownDiameterM);
    expect(bouge.kind).toBe('arbre');
    expect(bouge.id).toBe('e1');
  });

  it('l’EMPRISE explicite suit le déplacement (elle ne reste pas derrière)', () => {
    const o = {
      ...newEnvironmentObject('e2', 'batiment', [-7.6, 33.49]),
      footprint: [
        [-7.6001, 33.4899],
        [-7.5999, 33.4899],
        [-7.5999, 33.4901],
        [-7.6001, 33.4901],
      ] as [number, number][],
    };
    const bouge = deplacerEnvironment(o, [-7.5, 33.4]);
    expect(bouge.footprint).toHaveLength(4);
    bouge.footprint!.forEach((p, i) => {
      expect(p[0]).toBeCloseTo(o.footprint[i][0] + (-7.5 - -7.6), 10);
      expect(p[1]).toBeCloseTo(o.footprint[i][1] + (33.4 - 33.49), 10);
    });
  });

  it('ne modifie PAS l’objet d’origine (transformation pure)', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.49]);
    deplacerEnvironment(o, [-7.5, 33.4]);
    expect(o.centerLng).toBe(-7.6);
    expect(o.centerLat).toBe(33.49);
  });

  it('un point illisible ne déplace RIEN', () => {
    const o = newEnvironmentObject('e1', 'arbre', [-7.6, 33.49]);
    expect(deplacerEnvironment(o, [Number.NaN, 33.4])).toBe(o);
    expect(deplacerEnvironment(o, [-7.5, Number.NaN])).toBe(o);
  });

  it('un objet SANS hauteur saisie ne porte toujours AUCUNE ombre après déplacement', () => {
    const o = withCrownDiameter(newEnvironmentObject('e1', 'arbre', [-7.6, 33.49]), 5);
    const bouge = deplacerEnvironment(o, [-7.5987, 33.4996]);
    expect(bouge.heightM).toBeUndefined();
    expect(environmentShadeEntries([bouge], origin)).toEqual([]);
  });

  it('une ombre existante repart bien de la NOUVELLE position', () => {
    const o = withCrownDiameter(withEnvHeight(newEnvironmentObject('e1', 'arbre', [-7.6, 33.49]), 8), 5);
    const avant = environmentShadeEntries([o], origin);
    const apres = environmentShadeEntries([deplacerEnvironment(o, [-7.59, 33.495])], origin);
    expect(avant).toHaveLength(1);
    expect(apres).toHaveLength(1);
    expect(apres[0].x).not.toBeCloseTo(avant[0].x, 3);
    expect(apres[0].effHeightM).toBe(avant[0].effHeightM); // la hauteur saisie n'a pas bougé
  });
});
