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

/** La tuile « Tracé libre » : le tracé au clic est le mode de dessin EXISTANT ; elle le dit, rien n'est découpé. */
export const MOTIF_TRACE_LIBRE = {
  ouvert: 'Tracé libre : cliquez sur la carte pour poser chaque coin du toit, puis « Terminer le tracé ».',
  ferme: 'Tracé libre : le contour reste tel que tracé — glissez un coin pour le déplacer.',
} as const;

export type VerdictForme = { ok: true; pans: AreaRecord[] } | { ok: false; motif: string };

/** Ce que la déduction de forme lit d'un pan (un `AreaRecord` convient). */
export interface PanForme {
  id: string;
  vertices?: readonly LngLat[];
  roofType?: string;
  facingAzimuthDeg?: number;
}

const EPS_DEG = 1e-6; // ~1 cm : deux sommets d'une même découpe sont le même point
const memePoint = (a: LngLat, b: LngLat): boolean => Math.abs(a[0] - b[0]) < EPS_DEG && Math.abs(a[1] - b[1]) < EPS_DEG;
const sommetsUniques = (v: readonly LngLat[]): LngLat[] => v.filter((p, i) => v.findIndex((q) => memePoint(p, q)) === i);
const ecartAzimut = (a: number, b: number): number => {
  const d = (((a - b) % 360) + 360) % 360;
  return Math.min(d, 360 - d);
};
const ecartAuSudDeg = (face: number): number => ecartAzimut(face, 180); // ACAL1510

/**
 * Maquette Main — la tuile d'un toit ROUVERT : le document ne garde aucune « forme », mais ses pans la portent
 * quand elle est sans ambiguïté. Un pan plat → « Plat » ; un pan en pente → « 1 pan » ; deux pans en pente qui
 * partagent une arête (deux sommets) et se tournent le dos (± 30°) → « 2 pans » ; des triangles en pente qui
 * partagent tous un même sommet (le centre de la croupe) → « 4 pans ». Tout le reste (L, T, pans séparés…)
 * → `null` : aucune tuile n'est choisie plutôt qu'une forme que la géométrie ne soutient pas.
 */
export function formeDuToit(pans: readonly PanForme[]): RoofShapePreset | null {
  const traces = pans
    .map((p) => ({ ...p, sommets: sommetsUniques(p.vertices ?? []) }))
    .filter((p) => p.sommets.length >= 3);
  if (traces.length === 0) return null;
  if (traces.length === 1) {
    const t = traces[0].roofType;
    return t === 'flat' ? 'flat' : t === 'pitched' ? 'shed' : null;
  }
  if (traces.some((p) => p.roofType !== 'pitched')) return null;
  if (traces.length === 2) {
    const [a, b] = traces;
    const arete = a.sommets.filter((p) => b.sommets.some((q) => memePoint(p, q))).length >= 2;
    const dos = Number.isFinite(a.facingAzimuthDeg) && Number.isFinite(b.facingAzimuthDeg)
      && Math.abs(ecartAzimut(a.facingAzimuthDeg as number, b.facingAzimuthDeg as number) - 180) <= 30;
    return arete && dos ? 'gable' : null;
  }
  if (traces.every((p) => p.sommets.length === 3)) {
    const centre = traces[0].sommets.find((c) => traces.every((p) => p.sommets.some((q) => memePoint(c, q))));
    if (centre) return 'hip';
  }
  return null;
}

/** Découpe `contour` selon `forme`, à la pente SAISIE. Refus nommé, jamais de découpage faux. */
export function decouperContour(
  contour: readonly LngLat[],
  forme: RoofShapePreset,
  penteDeg: number,
  existants: readonly { id: string }[],
): VerdictForme {
  if (contour.length < 3) return { ok: false, motif: 'Forme du toit : fermez d’abord le contour du pan.' };
  try {
    // ACAL1510 — le pan le mieux exposé d'abord (tri stable) : c'est lui que l'atelier CHARGE. « Créer le toit » commence au
    // nord-ouest, et le premier pan de la croupe regardait le nord : 0 module, 0 kWc, aucune cause.
    const decoupes = generateRoofShapePans([...contour], forme)
      .map((d, i) => ({ d, i })).sort((a, b) => ecartAuSudDeg(a.d.facingAzimuthDeg) - ecartAuSudDeg(b.d.facingAzimuthDeg) || a.i - b.i).map((x) => x.d);
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

/** ACAL1735 — confirmer la pente d'un pan d'une découpe la confirme pour les pans de la MÊME découpe qui avaient la même pente
 *  (`avantDeg`) et aucune provenance : ils suivent (pente + `pitchSource`). Un pan d'une autre pente, déjà confirmé, ou hors
 *  découpe n'est jamais touché. Rend les ids modifiés. */
export function propagerPenteDecoupe(
  pans: ReadonlyArray<{ id: string; roofType: string; pitchDeg: number; pitchSource?: Record<string, unknown> }>,
  idsDecoupe: ReadonlySet<string>,
  idActif: string,
  avantDeg: number,
  apresDeg: number,
  source: Record<string, unknown>,
): string[] {
  const touches: string[] = [];
  if (!idsDecoupe.has(idActif)) return touches;
  for (const p of pans) {
    if (p.id === idActif || !idsDecoupe.has(p.id) || p.roofType !== 'pitched' || p.pitchDeg !== avantDeg
      || (p.pitchSource && !(p.pitchSource.mode === 'degres' && p.pitchSource.degres === avantDeg))) continue; // un pan déjà confirmé à cette pente suit aussi (curseur)
    p.pitchDeg = apresDeg;
    p.pitchSource = JSON.parse(JSON.stringify(source)) as Record<string, unknown>;
    touches.push(p.id);
  }
  return touches;
}

export interface FormesToitDeps {
  /** Le bouton « + Ajouter une zone » : les puces se posent juste après. */
  ancre: HTMLElement | null;
  /** Contour du pan actif, [] tant qu'il n'est pas fermé. */
  contour: () => readonly LngLat[];
  pente: () => number;
  /** Les pans de l'atelier (ids pour la découpe ; contour, type et face pour la tuile d'un toit rouvert). */
  existants: () => readonly PanForme[];
  /** Nombre d'obstacles du pan actif (la découpe les perdrait : refus). */
  obstacles: () => number;
  /** Remplace le pan actif par les pans découpés (charge le premier, rafraîchit la liste). */
  appliquer: (pans: AreaRecord[]) => void;
  setStatus: (msg: string) => void;
}

/** Monte la rangée de puces ; `rafraichir` la montre seulement contour fermé. Dans l'atelier plein écran
 *  (ancre sous `.cal-coque`, maquette Main) : tuiles (pictogrammes en CSS) toujours visibles, « Tracé libre », état choisi
 *  (`aria-pressed`, dernière forme appliquée), découpes marquées `aria-disabled` tant que le contour est ouvert.
 *  Hors coque (mode lead) : les mêmes puces texte qu'avant. */
export function monterFormesToit(deps: FormesToitDeps): {
  rafraichir: () => void;
  cliquer: (f: RoofShapePreset) => VerdictForme;
} {
  let choisie: RoofShapePreset | 'libre' | null = null;
  let deduite: RoofShapePreset | null = null; // la forme que portent les pans rouverts (`formeDuToit`)
  let etaitFerme = false;
  let marquer = (): void => {};
  // T4-U2-005 — la forme choisie AVANT tout contour (ordre de la maquette Main : Forme, puis Dimensions) : retenue, puis
  // appliquée quand le contour se ferme (« Créer le toit » ou un tracé fermé). Avant, les tuiles restaient grisées.
  let enAttente: RoofShapePreset | null = null;
  const cliquer = (forme: RoofShapePreset): VerdictForme => {
    if (deps.contour().length < 3 && deps.obstacles() === 0) {
      enAttente = forme;
      choisie = forme;
      marquer();
      const libelle = FORMES_TOIT.find((f) => f.forme === forme)?.libelle ?? forme;
      const motif = `Forme « ${libelle} » choisie : saisissez la longueur et la largeur puis « Créer le toit » — il sera découpé dans cette forme.`;
      deps.setStatus(motif);
      return { ok: false, motif };
    }
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
  /** T4-U2-005 — le contour vient de se fermer : la forme retenue s'applique, une fois. */
  const appliquerEnAttente = () => {
    if (!enAttente || deps.contour().length < 3) return;
    const forme = enAttente;
    enAttente = null;
    cliquer(forme);
  };
  const ancre = deps.ancre;
  if (!ancre || typeof document === 'undefined' || !ancre.parentElement) return { rafraichir: appliquerEnAttente, cliquer };
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
    b.textContent = libelle; // coque : le pictogramme est dessiné par 51-etape-toit.css (masque, `currentColor`)
    if (enCoque) b.setAttribute('aria-pressed', 'false');
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
    marquer = () => tuiles.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.forme === (choisie ?? deduite))));
  }
  ancre.insertAdjacentElement('afterend', rangee);
  return {
    rafraichir: () => {
      const ferme = deps.contour().length >= 3;
      rangee.hidden = !enCoque && !ferme;
      if (!enCoque) return;
      if (etaitFerme && !ferme) choisie = null; // contour effacé ou nouveau pan : plus de forme appliquée
      etaitFerme = ferme;
      deduite = ferme ? formeDuToit(deps.existants()) : null;
      // T4-U2-005 — les tuiles restent choisissables avant le contour ; la bulle dit l'ordre.
      for (const b of tuiles) {
        if (b.dataset.forme === 'libre') continue;
        b.removeAttribute('aria-disabled');
        if (ferme) b.removeAttribute('title');
        else b.title = 'Choisissez la forme, puis saisissez la longueur et la largeur et « Créer le toit ».';
      }
      marquer();
      appliquerEnAttente();
    },
    cliquer,
  };
}
