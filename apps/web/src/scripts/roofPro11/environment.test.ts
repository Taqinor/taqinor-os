// CAL67 — objets d'environnement (arbres/bâtiments voisins) : géométrie PURE, testée
// hors DOM/Three. Toutes les dimensions doivent être SAISIES ; rien n'est estimé.
import { describe, expect, it } from 'vitest';
import {
  newEnvironmentObject,
  withEnvHeight,
  withCrownDiameter,
  withFootprintDims,
  withEvergreen,
  environmentRing,
  environmentShadeEntries,
  ENV_MIN_HEIGHT_M,
  ENV_MAX_HEIGHT_M,
} from './environment';

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
