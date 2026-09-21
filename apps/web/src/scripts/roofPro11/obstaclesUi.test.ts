// CALX91 — GESTES SUR LES SOMMETS D'UN CONTOUR FERMÉ. La géométrie (projeté orthogonal,
// refus de suppression) est prouvée dans `snap.test.ts` ; ce fichier couvre la DÉCISION que
// `obstaclesUi.ts` prend avant d'agir : Alt maintenue = suppression et JAMAIS un glissé, et
// aucun geste sommet hors des gardes déjà en place (contour fermé, hors mode obstacle /
// disposition) — donc le comportement d'aujourd'hui tant qu'Alt n'est pas maintenue.
import { describe, expect, it } from 'vitest';
import { gesteSommet } from './obstaclesUi';

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
