// H6 (maquettes 22/11) — MODE PRÉSENTATION de la carte (« Montrer au client », maquette TelephoneClient) :
// l'écran hôte montre l'atelier au client, en lecture seule. Tout marqueur d'ÉDITION se tait — poignées des coins
// (calque `rp9-pts` et sphères 3D de `poigneesSommets3d`), tracé pointillé, cotes, étiquettes, retraits, repères —
// et UN doigt fait tourner la maison (cap), au lieu de déplacer la carte. Rien n'est écrit : ni géométrie, ni
// document, ni brouillon ; la caméra n'est pas sérialisée. Le site public et l'atelier ordinaire ne l'appellent pas.

/** Calques qui ne servent qu'à éditer : masqués en présentation, rendus tels quels à la sortie. */
export const CALQUES_EDITION = [
  'rp9-pts', 'rp9-line', 'rp9-mesure-line', 'rp9-mesure-label', 'rp9-obs-label', 'rp9-obs-preview',
  'rp9-ref-contour-fill', 'rp9-ref-contour-line', 'rp9-zones-label', 'rp9-reperes-cercle', 'rp9-reperes-point',
  'rp9-setback-lateral', 'rp9-setback-extremity', 'rp9-setback-parapet', 'rp9-setback-joint',
] as const;

/** Degrés de cap par pixel glissé d'un doigt. */
const DEG_PAR_PX = 0.4;

export interface CartePresentable {
  getLayer?(id: string): unknown;
  getLayoutProperty?(id: string, nom: string): unknown;
  setLayoutProperty?(id: string, nom: string, valeur: 'visible' | 'none'): unknown;
  triggerRepaint?(): void;
  on?(type: string, fn: () => void): unknown;
  off?(type: string, fn: () => void): unknown;
  getBearing?(): number;
  setBearing?(cap: number): unknown;
  getCanvasContainer?(): HTMLElement;
  dragPan?: { enable(): unknown; disable(): unknown };
}

interface Etat { actif: boolean; avant: Map<string, unknown>; ecouteurs: Set<() => void>; quitter: (() => void) | null }
const etats = new WeakMap<object, Etat>();
const etatDe = (map: object): Etat => {
  let e = etats.get(map);
  if (!e) { e = { actif: false, avant: new Map(), ecouteurs: new Set(), quitter: null }; etats.set(map, e); }
  return e;
};

/** Vrai quand la carte est montrée au client (aucun marqueur d'édition). */
export const enPresentation = (map: object): boolean => etats.get(map)?.actif === true;

/** Un module de scène (poignées 3D) se ré-applique à chaque bascule. */
export function surPresentation(map: object, fn: () => void): void { etatDe(map).ecouteurs.add(fn); }

/** Masque les calques d'édition présents (ceux ajoutés plus tard le sont au prochain `idle`). */
function taire(map: CartePresentable, e: Etat): void {
  for (const id of CALQUES_EDITION) {
    if (!map.getLayer?.(id)) continue;
    const vis = map.getLayoutProperty?.(id, 'visibility');
    if (!e.avant.has(id)) e.avant.set(id, vis ?? 'visible');
    if (vis !== 'none') map.setLayoutProperty?.(id, 'visibility', 'none');
  }
}

/** UN doigt (ou le bouton principal) fait tourner la maison ; deux doigts restent à la carte (pincer). */
function tournerUnDoigt(map: CartePresentable): () => void {
  const el = map.getCanvasContainer?.();
  if (!el || !map.setBearing || !map.getBearing) return () => {};
  const doigts = new Set<number>();
  let depart: { x: number; cap: number } | null = null;
  const bas = (ev: PointerEvent) => {
    doigts.add(ev.pointerId);
    try { el.setPointerCapture?.(ev.pointerId); } catch { /* pointeur déjà relâché */ }
    depart = doigts.size === 1 && ev.button === 0 ? { x: ev.clientX, cap: map.getBearing!() } : null;
  };
  const bouge = (ev: PointerEvent) => { if (depart && doigts.has(ev.pointerId)) map.setBearing!(depart.cap - (ev.clientX - depart.x) * DEG_PAR_PX); };
  const haut = (ev: PointerEvent) => { doigts.delete(ev.pointerId); depart = null; };
  el.addEventListener('pointerdown', bas);
  el.addEventListener('pointermove', bouge);
  for (const t of ['pointerup', 'pointercancel'] as const) el.addEventListener(t, haut);
  map.dragPan?.disable();
  return () => {
    el.removeEventListener('pointerdown', bas);
    el.removeEventListener('pointermove', bouge);
    for (const t of ['pointerup', 'pointercancel'] as const) el.removeEventListener(t, haut);
    map.dragPan?.enable();
  };
}

/** Entre (vrai) ou sort (faux) du mode présentation ; rend l'état posé. Idempotent. */
export function poserPresentation(map: CartePresentable, actif: boolean): boolean {
  const e = etatDe(map);
  if (e.actif === actif) return actif;
  e.actif = actif;
  const veiller = () => { if (e.actif) taire(map, e); };
  if (actif) {
    taire(map, e);
    map.on?.('idle', veiller);
    const finRotation = tournerUnDoigt(map);
    e.quitter = () => { map.off?.('idle', veiller); finRotation(); };
  } else {
    e.quitter?.();
    e.quitter = null;
    for (const [id, vis] of e.avant) if (map.getLayer?.(id)) map.setLayoutProperty?.(id, 'visibility', vis === 'none' ? 'none' : 'visible');
    e.avant.clear();
  }
  e.ecouteurs.forEach((fn) => fn());
  map.triggerRepaint?.();
  return actif;
}
