// ACAL549 — LA CAUSE MESURÉE D'UN PAN OÙ AUCUN MODULE NE TIENT (contrat ACAL555 `motifsPansVides`).
// `causeDuPanVide` est PURE : elle reçoit des mesures prises dans la MÊME passe de pavage et rend la
// PREMIÈRE cause vraie, testée dans cet ordre (cette tâche en est la seule propriétaire) :
// retrait de rive → obstacles → seuil d'accès solaire → module trop grand → inconnue. Aucun défaut :
// une mesure absente (`null`) rend sa cause intestable, jamais vraie.
import { resolveSetbacks, type Panel2Module, type PerimeterSetbacks } from '../../lib/roofPro2';
import { type PackResult, type PanelGrid } from '../../lib/estimatorBrainV2';
import { nomDeFace } from './hypotheses'; // ACAL1970 — le nom de la face, vocabulaire partagé

export type CodeMotifPanVide = 'retrait_rive' | 'obstacles' | 'seuil_acces_solaire' | 'module_trop_grand' | 'orientation_nord' | 'inconnue';
export interface MotifPanVide { code: CodeMotifPanVide; message: string; mesures: Record<string, number> }
export interface MesuresPanVide {
  largeurPanM: number; retraitM: number | null; coteCourtM: number; coteLongM: number;
  aireM2: number; surfacePosableM2: number; candidats: number; seuil: number | null; ecartes: number;
}

export const CLE_MOTIFS_PANS_VIDES = 'motifsPansVides';
const r2 = (v: number): number => Math.round(v * 100) / 100;
const fr = (v: number, d = 2): string => v.toFixed(d).replace('.', ',');

/** Plus petite largeur (m) d'un contour en mètres : étendue minimale perpendiculaire à ses arêtes. */
export function largeurMinimaleM(ringENU: readonly [number, number][]): number {
  let min = Infinity;
  for (let i = 0; i < ringENU.length; i++) {
    const [ax, ay] = ringENU[i];
    const [bx, by] = ringENU[(i + 1) % ringENU.length];
    const l = Math.hypot(bx - ax, by - ay);
    if (l < 1e-9) continue;
    const [nx, ny] = [-(by - ay) / l, (bx - ax) / l];
    const proj = ringENU.map(([x, y]) => x * nx + y * ny);
    min = Math.min(min, Math.max(...proj) - Math.min(...proj));
  }
  return Number.isFinite(min) ? min : 0;
}

/** Le plus petit des retraits de rive RÉELLEMENT passés au pavage (latéral / extrémité / acrotère). */
export function retraitApplique(setbacks: Partial<PerimeterSetbacks> | undefined, setbackM: number): number {
  const s = resolveSetbacks(setbacks, setbackM);
  return Math.min(s.lateralM, s.extremityM, s.parapetM);
}

/** Mesures d'un pavage vide, toutes lues sur le pack rendu (aucune valeur par défaut). */
export function mesurerPanVide(pack: PackResult, grid: PanelGrid, retraitM: number | null, module: Panel2Module,
  filtrage: { ecartes: number[]; seuilApplique: number | null } | null): MesuresPanVide {
  return {
    largeurPanM: largeurMinimaleM(pack.ringENU), retraitM, coteCourtM: module.courtM, coteLongM: module.longM,
    aireM2: pack.areaM2, surfacePosableM2: pack.usableAreaM2, candidats: grid.panels.length,
    seuil: filtrage?.seuilApplique ?? null, ecartes: filtrage?.ecartes.length ?? 0,
  };
}

export function causeDuPanVide(m: MesuresPanVide): MotifPanVide {
  const utile = Math.max(0, m.largeurPanM - 2 * (m.retraitM ?? 0));
  if (m.retraitM != null && m.retraitM > 0 && utile < m.coteCourtM) {
    // ACAL1966 — anneau posable VIDE : aucune largeur à citer (« 0,00 m sur 0,00 m » n'est pas une mesure du pan).
    const message = m.largeurPanM > 0
      ? `Aucun module : le retrait de rive (${fr(m.retraitM)} m de chaque côté) ne laisse que ${fr(utile)} m sur ${fr(m.largeurPanM)} m de large`
      : `Aucun module : aucun anneau posable — le retrait de rive (${fr(m.retraitM)} m de chaque côté) ne laisse aucune surface sur ce pan`;
    return { code: 'retrait_rive',
      message,
      mesures: { retraitM: r2(m.retraitM), largeurPanM: r2(m.largeurPanM), largeurUtileM: r2(utile), coteModuleM: r2(m.coteCourtM) } };
  }
  if (m.aireM2 > 0 && m.surfacePosableM2 <= 1e-6) {
    return { code: 'obstacles', message: `Aucun module : les obstacles et zones couvrent les ${fr(m.aireM2, 1)} m² du pan`,
      mesures: { surfacePosableM2: 0 } };
  }
  if (m.seuil != null && m.candidats > 0 && m.ecartes >= m.candidats) {
    return { code: 'seuil_acces_solaire',
      message: `Aucun module : le seuil d'accès solaire de ${Math.round(m.seuil * 100)} % a écarté les ${m.ecartes} emplacements`,
      mesures: { seuil: m.seuil, ecartes: m.ecartes } };
  }
  if (m.candidats === 0) {
    return { code: 'module_trop_grand',
      message: `Aucun module : le module (${fr(m.coteLongM)} × ${fr(m.coteCourtM)} m) ne tient pas dans la surface posable (${fr(m.surfacePosableM2, 1)} m²)`,
      mesures: { coteModuleM: r2(m.coteCourtM), surfacePosableM2: r2(m.surfacePosableM2) } };
  }
  return { code: 'inconnue', message: "Aucun module posé — la cause n'a pas pu être déterminée", mesures: {} };
}

/** ACAL1970 — chemin « toit en pente » : pan tourné au nord (le solveur le dit, `northFacing`), aucun module posé
 *  alors qu'un besoin existe ⇒ la cause `orientation_nord` (contrat ACAL1969 : mesures `azimutDeg`, `penteDeg`) ;
 *  sinon `null` (le motif noté du pan est alors retiré, comme sur le chemin plat). */
export function motifPenteNord(nordique: boolean, poses: number, besoin: number, azimutDeg: number, penteDeg: number): MotifPanVide | null {
  if (!nordique || poses > 0 || !(besoin > 0) || !Number.isFinite(azimutDeg) || !Number.isFinite(penteDeg)) return null;
  // Schéma : `azimutDeg` dans [0, 360[ (359,996 arrondi donnerait 360, refusé), `penteDeg` dans [0, 90].
  const azimut = ((r2(azimutDeg) % 360) + 360) % 360;
  const pente = Math.min(90, Math.max(0, r2(penteDeg)));
  const nom = nomDeFace(azimut);
  // « au nord » seulement pour un pan vraiment nord ; les autres faces de la moitié nord disent la leur (même
  // vocabulaire que `hypotheses.ts`, et « trop au nord » comme la phrase du pan du toit en pente).
  const face = nom === 'Nord' ? 'orienté au nord' : `orienté ${nom.toLowerCase()}`;
  return { code: 'orientation_nord',
    message: `Aucun module : pan en pente (${Math.round(pente)}°) ${face} (azimut ${Math.round(azimut) % 360}°)${nom === 'Nord' ? '' : ', trop au nord'}`, // sans point final, comme les autres causes (la note en ajoute un)
    mesures: { azimutDeg: azimut, penteDeg: pente } };
}

// — Mémoire d'atelier : un motif par pan, semée depuis le document, écrite à la sérialisation. —
const memoire = new Map<string, MotifPanVide>();

/** Note (ou retire, `null`) le motif d'un pan ; rend le motif noté. */
export function noterMotifPanVide(panId: string | null | undefined, motif: MotifPanVide | null): MotifPanVide | null {
  if (panId) { if (motif) memoire.set(panId, motif); else memoire.delete(panId); }
  return motif;
}

/** À L'OUVERTURE — la mémoire repart de ce que le document porte (rien ⇒ mémoire vide). */
export function semerMotifsDepuisDocument(json: unknown): void {
  memoire.clear();
  const brut = (json as Record<string, unknown> | null | undefined)?.[CLE_MOTIFS_PANS_VIDES];
  if (!brut || typeof brut !== 'object' || Array.isArray(brut)) return;
  for (const [id, m] of Object.entries(brut as Record<string, MotifPanVide>)) {
    if (m && typeof m.code === 'string' && typeof m.message === 'string') memoire.set(id, JSON.parse(JSON.stringify(m)));
  }
}

/** ACAL1970 — la pose d'un pan (positions et faces, sans numéros) : la même empreinte que
 *  `prefill.ts::pansPavesDansLaSession` (ACAL307) pour dire « pavé dans la session ». */
const empreintePose = (panels: unknown): string => JSON.stringify((Array.isArray(panels) ? panels : [])
  .map((p: { cx?: number; cy?: number; face?: string }) => [p?.cx, p?.cy, p?.face ?? null]));

/** ACAL1970 — un pan que la session n'a ni retouché ni re-résolu par un geste : même forme, même besoin et même
 *  pose que dans le document relu (ACAL31). Son motif repart TEL QU'IL A ÉTÉ LU (présent ou absent) : la
 *  résolution de fond de l'ouverture peut le montrer à l'écran, jamais l'écrire ni l'effacer. */
function panInchange(z: Record<string, unknown>, rz: Record<string, unknown> | undefined): boolean {
  if (!rz) return false;
  const meme = (k: string) => JSON.stringify(z[k] ?? null) === JSON.stringify(rz[k] ?? null);
  const besoin = (z.neededAuto === true && rz.neededAuto === true) || meme('neededPanels');
  return ['vertices', 'roofType', 'pitchDeg', 'facingAzimuthDeg', 'neededAuto'].every(meme) && besoin
    && empreintePose((z.geometry as { panels?: unknown } | undefined)?.panels) === empreintePose((rz.geometry as { panels?: unknown } | undefined)?.panels);
}

/** À LA SÉRIALISATION — un motif par pan VIDE du dessin ; aucun ⇒ la clé est retirée. ACAL1970 — `relu` (le
 *  document rouvert) : un pan inchangé garde le motif LU ; seul un pan touché dans la session écrit le sien. */
export function ecrireMotifsDansDocument(layout: unknown, relu?: Record<string, unknown> | null): boolean {
  const cible = layout as Record<string, unknown> | null | undefined;
  if (!cible || typeof cible !== 'object') return false;
  const sortie: Record<string, MotifPanVide> = {};
  const lus = (relu?.[CLE_MOTIFS_PANS_VIDES] ?? {}) as Record<string, MotifPanVide>;
  const zonesRelues = new Map((Array.isArray(relu?.zones) ? (relu!.zones as Array<Record<string, unknown>>) : [])
    .map((z) => [z?.id, z]));
  for (const z of Array.isArray(cible.zones) ? (cible.zones as Array<Record<string, unknown>>) : []) {
    const g = (z?.geometry ?? {}) as { count?: number; panels?: unknown[] };
    const garni = Number(g.count) > 0 || (Array.isArray(g.panels) && g.panels.length > 0);
    const inchange = relu != null && typeof z?.id === 'string' && panInchange(z, zonesRelues.get(z.id));
    const m = typeof z?.id === 'string' ? (inchange ? lus[z.id] : memoire.get(z.id)) : undefined;
    if (m && (inchange || !garni)) sortie[z.id as string] = JSON.parse(JSON.stringify(m));
  }
  if (Object.keys(sortie).length === 0) { delete cible[CLE_MOTIFS_PANS_VIDES]; return false; }
  cible[CLE_MOTIFS_PANS_VIDES] = sortie;
  return true;
}
