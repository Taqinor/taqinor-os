/**
 * ACAL410 — « FORME DU TOIT » : UN CLIC DÉCOUPE LE CONTOUR FERMÉ EN PANS.
 *
 * `generateRoofShapePans` (scene3d.ts) et `buildAreasFromShape` (zones.ts) savaient déjà
 * découper un contour en 2/4 pans, en L ou en T, mais aucun geste ne les appelait : chaque
 * pan se dessinait à la main. Ce module ne contient AUCUNE géométrie neuve : il enchaîne ces
 * deux fonctions et pose des puces près de « + Ajouter une zone ».
 *
 * La pente appliquée est celle SAISIE (`pente()`), jamais une valeur posée ici. Un refus
 * (contour convexe pour L/T, contour illisible, pan portant des obstacles) NOMME sa raison
 * et ne change rien.
 */
import type { LngLat } from '../../lib/roof';
import { areaLabel, type AreaRecord } from '../../lib/roofAreas';
import { generateRoofShapePans, type RoofShapePreset } from './scene3d';
import { buildAreasFromShape, prochainId } from './zones';

export const FORMES_TOIT: ReadonlyArray<{ forme: RoofShapePreset; libelle: string }> = [
  { forme: 'flat', libelle: 'Plat' },
  { forme: 'shed', libelle: '1 pan' },
  { forme: 'gable', libelle: '2 pans' },
  { forme: 'hip', libelle: '4 pans' },
  { forme: 'l_gable', libelle: 'L' },
  { forme: 't_gable', libelle: 'T' },
];

export type VerdictForme = { ok: true; pans: AreaRecord[] } | { ok: false; motif: string };

/** Découpe `contour` selon `forme`, à la pente SAISIE. Refus nommé, jamais de découpage faux. */
export function decouperContour(
  contour: readonly LngLat[],
  forme: RoofShapePreset,
  penteDeg: number,
  existants: readonly { id: string }[],
): VerdictForme {
  if (contour.length < 3) return { ok: false, motif: 'Forme du toit : fermez d’abord le contour du pan.' };
  try {
    const decoupes = generateRoofShapePans([...contour], forme);
    if (!decoupes.length) return { ok: false, motif: 'Forme du toit : ce contour ne donne aucun pan.' };
    const pris: { id: string }[] = [...existants];
    const pans = buildAreasFromShape(decoupes, forme, penteDeg, () => {
      const id = prochainId('area', pris);
      pris.push({ id });
      return id;
    });
    for (const p of pans) p.label = areaLabel(Number(p.id.slice('area-'.length)) - 1);
    return { ok: true, pans };
  } catch (e) {
    return { ok: false, motif: e instanceof Error ? e.message : 'Forme du toit : découpe impossible.' };
  }
}

export interface FormesToitDeps {
  /** Le bouton « + Ajouter une zone » : les puces se posent juste après. */
  ancre: HTMLElement | null;
  /** Contour du pan actif, [] tant qu'il n'est pas fermé. */
  contour: () => readonly LngLat[];
  pente: () => number;
  existants: () => readonly { id: string }[];
  /** Nombre d'obstacles du pan actif (la découpe les perdrait : refus). */
  obstacles: () => number;
  /** Remplace le pan actif par les pans découpés (charge le premier, rafraîchit la liste). */
  appliquer: (pans: AreaRecord[]) => void;
  setStatus: (msg: string) => void;
}

/** Monte la rangée de puces ; `rafraichir` la montre seulement contour fermé. */
export function monterFormesToit(deps: FormesToitDeps): {
  rafraichir: () => void;
  cliquer: (f: RoofShapePreset) => VerdictForme;
} {
  const cliquer = (forme: RoofShapePreset): VerdictForme => {
    const verdict: VerdictForme =
      deps.obstacles() > 0
        ? { ok: false, motif: 'Forme du toit : ce pan porte des obstacles — retirez-les avant de le découper.' }
        : decouperContour(deps.contour(), forme, deps.pente(), deps.existants());
    if (verdict.ok) {
      deps.appliquer(verdict.pans);
      deps.setStatus(`Toit découpé en ${verdict.pans.length} pan${verdict.pans.length > 1 ? 's' : ''}.`);
    } else deps.setStatus(verdict.motif);
    return verdict;
  };
  const ancre = deps.ancre;
  if (!ancre || typeof document === 'undefined' || !ancre.parentElement) return { rafraichir: () => {}, cliquer };
  const rangee = document.createElement('div');
  rangee.id = 'rp9-formes-toit';
  rangee.className = 'mt-2 flex flex-wrap items-center gap-1';
  rangee.setAttribute('role', 'group');
  rangee.setAttribute('aria-label', 'Forme du toit');
  rangee.hidden = true;
  for (const { forme, libelle } of FORMES_TOIT) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'rp9-chip';
    b.dataset.forme = forme;
    b.textContent = libelle;
    b.addEventListener('click', () => void cliquer(forme));
    rangee.appendChild(b);
  }
  ancre.insertAdjacentElement('afterend', rangee);
  return { rafraichir: () => (rangee.hidden = deps.contour().length < 3), cliquer };
}
