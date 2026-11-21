// ACAL717 — courbe « direct perdu » : l'attendu est calculé ICI par la formule de hauteur du soleil,
// jamais par `hourlyShadeFactors`.
import { describe, expect, it } from 'vitest';
import { directPerduParHeure, phraseDirectPerdu, svgCourbeDirectPerdu } from './courbeDirectPerdu';

const LAT = 33.57;
const JOUR = 349; // milieu de décembre
const hauteurSoleilDeg = (heure: number) => {
  const decl = (-23.44 * Math.cos((2 * Math.PI * (JOUR + 10)) / 365) * Math.PI) / 180;
  const phi = (LAT * Math.PI) / 180;
  const H = ((heure - 12) * 15 * Math.PI) / 180;
  return (Math.asin(Math.sin(phi) * Math.sin(decl) + Math.cos(phi) * Math.cos(decl) * Math.cos(H)) * 180) / Math.PI;
};
// Mur plein sud (y < 0) de 3 m à 8,24 m ; très long : couvre tous les azimuts de la journée.
const mur = [{ x: 0, y: -8.24, effHeightM: 3, halfWidthM: 200 }];
const modules = Array.from({ length: 10 }, (_, i) => ({ x: i * 0.01, y: 0 }));
const masque = Math.atan2(3, 8.24) * (180 / Math.PI); // ≈ 20°

describe('ACAL717 — directPerduParHeure', () => {
  it('décembre, mur au sud : 100 % sous 20° d’élévation, 0 % au-dessus, nuit = trou', () => {
    const s = directPerduParHeure(LAT, mur, modules, 11);
    expect(s).toHaveLength(24);
    s.forEach((v, h) => {
      const elev = hauteurSoleilDeg(h + 0.5);
      if (elev <= 0) expect(v).toBeNull();
      else expect(v).toBe(elev < masque ? 1 : 0);
    });
    expect(s[12]).toBe(0); // midi solaire : creux de la perte
    expect(s.some((v) => v === 1)).toBe(true);
  });
  it('la phrase tire ses heures de la courbe', () => {
    const s = directPerduParHeure(LAT, mur, modules, 11);
    const heures = s.flatMap((v, h) => (v === 1 ? [h] : []));
    expect(phraseDirectPerdu(s, 'Décembre')).toContain(`jusqu’à 100 % des modules entre ${heures[0]} h et ${heures[heures.length - 1] + 1} h solaire`);
  });
  it('sans obstruction : aucune perte (et le SVG ne trace pas de trait à zéro hors jour)', () => {
    const s = directPerduParHeure(LAT, [], modules, 11);
    expect(s.every((v) => v === null || v === 0)).toBe(true);
    expect(phraseDirectPerdu(s, 'Décembre')).toContain('aucun module');
    expect(svgCourbeDirectPerdu(s, 't')).toContain('<polyline');
  });
});
