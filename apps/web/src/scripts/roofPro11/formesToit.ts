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
  { forme: 'shed', libelle: '1 pan' }, // maquette Main : mode expert seulement (masqué en guidé par la coque)
  { forme: 'gable', libelle: '2 pans' },
  { forme: 'hip', libelle: '4 pans' },
  { forme: 'l_gable', libelle: 'En L' },
  { forme: 't_gable', libelle: 'En T' },
];

/** Maquette Main (22/11) — pictogrammes des tuiles (28 × 20, trait `currentColor`), tracés de la maquette. */
export const PICTOS_FORMES: Readonly<Record<RoofShapePreset | 'libre', string>> = {
  flat: '<rect x="2" y="3" width="24" height="14"/>',
  shed: '<rect x="2" y="3" width="24" height="14"/><path d="M2 17L26 3"/>',
  gable: '<rect x="2" y="3" width="24" height="14"/><path d="M2 10h24"/>',
  hip: '<rect x="2" y="3" width="24" height="14"/><path d="M2 3l7 7-7 7M26 3l-7 7 7 7M9 10h10"/>',
  l_gable: '<path d="M2 3h12v7h12v7H2z"/>',
  t_gable: '<path d="M2 3h24v7h-8v7h-8v-7H2z"/>',
  libre: '<path d="M3 16l6-12 8 9 8-6"/>',
};

/** La tuile « Tracé libre » : le tracé au clic est le mode de dessin EXISTANT ; elle le dit, rien n'est découpé. */
export const MOTIF_TRACE_LIBRE = {
  ouvert: 'Tracé libre : cliquez sur la carte pour poser chaque coin du toit, puis « Terminer le tracé ».',
  ferme: 'Tracé libre : le contour reste tel que tracé — glissez un coin pour le déplacer.',
} as const;

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

/** Le contenu d'une tuile de l'atelier plein écran : pictogramme (`display="none"` : invisible tant qu'aucune
 *  feuille de la coque ne le montre) puis le libellé — `textContent` reste le libellé seul. */
const contenuTuile = (forme: RoofShapePreset | 'libre', libelle: string): string =>
  `<svg class="rp9-forme-picto" display="none" width="28" height="20" viewBox="0 0 28 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">${PICTOS_FORMES[forme]}</svg><span>${libelle}</span>`;

/** Monte la rangée de puces ; `rafraichir` la montre seulement contour fermé. Dans l'atelier plein écran
 *  (ancre sous `.cal-coque`, maquette Main) : tuiles illustrées toujours visibles, « Tracé libre », état choisi
 *  (`aria-pressed`, dernière forme appliquée), découpes marquées `aria-disabled` tant que le contour est ouvert.
 *  Hors coque (mode lead) : les mêmes puces texte qu'avant. */
export function monterFormesToit(deps: FormesToitDeps): {
  rafraichir: () => void;
  cliquer: (f: RoofShapePreset) => VerdictForme;
} {
  let choisie: RoofShapePreset | 'libre' | null = null;
  let etaitFerme = false;
  let marquer = (): void => {};
  const cliquer = (forme: RoofShapePreset): VerdictForme => {
    const verdict: VerdictForme =
      deps.obstacles() > 0
        ? { ok: false, motif: 'Forme du toit : ce pan porte des obstacles — retirez-les avant de le découper.' }
        : decouperContour(deps.contour(), forme, deps.pente(), deps.existants());
    if (verdict.ok) {
      deps.appliquer(verdict.pans);
      deps.setStatus(`Toit découpé en ${verdict.pans.length} pan${verdict.pans.length > 1 ? 's' : ''}.`);
      choisie = forme;
      marquer();
    } else deps.setStatus(verdict.motif);
    return verdict;
  };
  const ancre = deps.ancre;
  if (!ancre || typeof document === 'undefined' || !ancre.parentElement) return { rafraichir: () => {}, cliquer };
  const enCoque = typeof ancre.closest === 'function' && ancre.closest('.cal-coque') !== null;
  const rangee = document.createElement('div');
  rangee.id = 'rp9-formes-toit';
  rangee.className = 'mt-2 flex flex-wrap items-center gap-1';
  rangee.setAttribute('role', 'group');
  rangee.setAttribute('aria-label', 'Forme du toit');
  if (enCoque) rangee.dataset.testid = 'cal-toit-formes';
  rangee.hidden = !enCoque; // coque : la grille reste visible (« Tracé libre » sert avant tout contour)
  const tuiles: HTMLButtonElement[] = [];
  const poser = (forme: RoofShapePreset | 'libre', libelle: string, surClic: () => void) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = enCoque ? 'rp9-chip rp9-tuile-forme' : 'rp9-chip';
    b.dataset.forme = forme;
    if (enCoque) {
      b.setAttribute('aria-pressed', 'false');
      b.innerHTML = contenuTuile(forme, libelle);
    } else b.textContent = libelle;
    b.addEventListener('click', surClic);
    rangee.appendChild(b);
    tuiles.push(b);
  };
  for (const { forme, libelle } of FORMES_TOIT) poser(forme, libelle, () => void cliquer(forme));
  if (enCoque) {
    poser('libre', 'Tracé libre', () => {
      choisie = 'libre';
      marquer();
      deps.setStatus(deps.contour().length >= 3 ? MOTIF_TRACE_LIBRE.ferme : MOTIF_TRACE_LIBRE.ouvert);
    });
    marquer = () => tuiles.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.forme === choisie)));
  }
  ancre.insertAdjacentElement('afterend', rangee);
  return {
    rafraichir: () => {
      const ferme = deps.contour().length >= 3;
      rangee.hidden = !enCoque && !ferme;
      if (!enCoque) return;
      if (etaitFerme && !ferme) choisie = null; // contour effacé ou nouveau pan : plus de forme appliquée
      etaitFerme = ferme;
      for (const b of tuiles) if (b.dataset.forme !== 'libre') b.setAttribute('aria-disabled', String(!ferme));
      marquer();
    },
    cliquer,
  };
}
