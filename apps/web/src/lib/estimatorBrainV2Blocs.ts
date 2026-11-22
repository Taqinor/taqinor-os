/**
 * ACAL583 — pavage en CHÂSSIS N × M (blocs de `rangs` rangs de `modulesParRang` modules) et pan vide.
 *
 * Fonctions PURES, voisines de `estimatorBrainV2.ts::packConfig` (qui ne grossit pas : fichier
 * ≥ 2 000 lignes). `packConfig` pave une cellule = le châssis entier, puis `developperChassis`
 * la développe en N × M panneaux. Sans l'option, ou à 1 × 1, rien de ce module n'intervient :
 * le résultat de `packConfig` est identique à l'octet.
 */
import type { ConfigFamily, PackedPanel, PackResult, PanelGrid } from './estimatorBrainV2';
import type { LngLat } from './roof';

const DEG2RAD = Math.PI / 180;

/** L'option `chassis` de `packConfig` (même forme que `zones[].chassis` du document, sans `source`). */
export interface OptionChassis {
  rangs: number;
  modulesParRang: number;
  /** Jeu HORIZONTAL au sol entre deux rangs d'un même châssis (m). */
  jeuEntreRangsM: number;
}

/** Ce que `PanelGrid.chassis` publie : combien de blocs entiers ont été posés. */
export interface ChassisPose {
  nombre: number;
  rangs: number;
  modulesParRang: number;
}

/** L'option réellement APPLICABLE : entiers ≥ 1, jeu fini ≥ 0, plus d'un module. Sinon `null`. */
export function chassisApplicable(c: OptionChassis | null | undefined): OptionChassis | null {
  if (!c) return null;
  const { rangs, modulesParRang, jeuEntreRangsM } = c;
  if (!Number.isInteger(rangs) || !Number.isInteger(modulesParRang) || rangs < 1 || modulesParRang < 1) return null;
  if (!Number.isFinite(jeuEntreRangsM) || jeuEntreRangsM < 0) return null;
  return rangs * modulesParRang > 1 ? c : null;
}

/** Dimensions du châssis : largeur le long de la rangée, longueur DE PENTE (le jeu au sol
 *  est ramené dans la pente : jeu ÷ cos de l'inclinaison). */
export function dimensionsChassis(
  c: OptionChassis,
  coteModulePenteM: number,
  largeurModuleM: number,
  colGapM: number,
  tiltDeg: number,
): { slopeLenM: number; rowWidthM: number } {
  const cosB = Math.cos(tiltDeg * DEG2RAD);
  return {
    rowWidthM: c.modulesParRang * largeurModuleM + (c.modulesParRang - 1) * colGapM,
    slopeLenM: c.rangs * coteModulePenteM + ((c.rangs - 1) * c.jeuEntreRangsM) / cosB,
  };
}

/** Développe chaque châssis posé (centre ENU) en `rangs × modulesParRang` panneaux. */
export function developperChassis(
  blocs: readonly PackedPanel[],
  c: OptionChassis,
  azimuthDeg: number,
  coteModulePenteM: number,
  largeurModuleM: number,
  colGapM: number,
  tiltDeg: number,
): PackedPanel[] {
  const az = azimuthDeg * DEG2RAD;
  const s: [number, number] = [Math.sin(az), Math.cos(az)]; // sens d'empilement (visée)
  const u: [number, number] = [-s[1], s[0]]; // axe des rangées
  const profondeur = coteModulePenteM * Math.cos(tiltDeg * DEG2RAD); // empreinte au sol d'un module
  const pasV = profondeur + c.jeuEntreRangsM;
  const pasU = largeurModuleM + colGapM;
  const sortie: PackedPanel[] = [];
  for (const b of blocs) {
    for (let i = 0; i < c.rangs; i++) {
      const dv = (i - (c.rangs - 1) / 2) * pasV;
      for (let j = 0; j < c.modulesParRang; j++) {
        const du = (j - (c.modulesParRang - 1) / 2) * pasU;
        sortie.push({ cx: b.cx + du * u[0] + dv * s[0], cy: b.cy + du * u[1] + dv * s[1] });
      }
    }
  }
  return sortie;
}

/** Pavage VIDE d'une orientation (aucun panneau) — sortie de `packConfig`, corps inchangé. */
function grilleVide(
  panelOrientation: 'portrait' | 'landscape',
  slopeLenM: number,
  rowWidthM: number,
  pitchM: number,
  beta: number,
): PanelGrid {
  return {
    panelOrientation,
    count: 0,
    kwc: 0,
    rowPitchM: pitchM,
    panels: [],
    slopeLenM,
    rowWidthM,
    footprintPerPanelM2: slopeLenM * Math.cos(beta) * rowWidthM,
  };
}

/** Le résultat de `packConfig` pour un contour de moins de 3 sommets (déplacé tel quel). */
export function panVide(p: {
  ring: LngLat[] | null | undefined;
  areaM2: number;
  usableAreaM2: number;
  azimuthDeg: number;
  tiltDeg: number;
  family: ConfigFamily;
  moduleLongM: number;
  moduleCourtM: number;
  pitchPortraitM: number;
  pitchLandscapeM: number;
}): PackResult {
  const beta = p.tiltDeg * DEG2RAD;
  const portrait = grilleVide('portrait', p.moduleLongM, p.moduleCourtM, p.pitchPortraitM, beta);
  const landscape = grilleVide('landscape', p.moduleCourtM, p.moduleLongM, p.pitchLandscapeM, beta);
  return {
    origin: p.ring?.[0] ?? [0, 0],
    ringENU: [],
    azimuthDeg: p.azimuthDeg,
    tiltDeg: p.tiltDeg,
    family: p.family,
    areaM2: p.areaM2,
    usableAreaM2: p.usableAreaM2,
    portrait,
    landscape,
    best: portrait,
  };
}
