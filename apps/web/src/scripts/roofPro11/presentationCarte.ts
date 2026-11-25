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
  'rp9-cotes', // ACAL1328 — cotes d'arêtes
  'rp9-contour-choisi', // ACAL2042 — contour or du toit choisi
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
  getCanvas?(): HTMLElement;
  dragPan?: { enable(): unknown; disable(): unknown };
  isMoving?(): boolean;
  getCenter?(): { lng: number; lat: number };
  getZoom?(): number;
  getPitch?(): number;
  setPadding?(p: { top: number; bottom: number; left: number; right: number }): unknown;
  project?(ll: [number, number]): { x: number; y: number };
  unproject?(p: [number, number]): { lng: number; lat: number };
}

/** J1 (tour 4) — la VUE TENUE de la présentation : la vue client s'ouvre de trois quarts et Y RESTE (atterrissage du
 *  boot, hydratation, cadrage, recalage tardif) jusqu'au premier geste de l'utilisateur sur la carte. */
export interface VueTenue {
  /** Pose la vue voulue + le cadrage (caméra seule) ; vrai quand le toit a pu être cadré (pans connus). */
  poser: () => boolean;
  /** Le cadrage seul (sans animation) ; faux tant que les pans ne sont pas connus (avant l'hydratation). */
  cadrer: () => boolean;
  /** Vrai quand la pente et le cap de la caméra sont ceux de la vue voulue. */
  atteinte: () => boolean;
  /** Appelée une fois : vue posée, toit cadré, carte au repos. */
  surPrete?: () => void;
  /** T4-V1-010 — le CENTRE de la maison `[lng, lat]` : le glisser la tourne autour de lui (elle reste où le cadrage
   *  l'a posée, dans la zone libre), jamais autour du centre de la caméra. `null` / absent : autour du centre. */
  pivot?: () => [number, number] | null;
}

/** Re-poses au plus (un module qui bougerait la caméra sans fin ne fait jamais tourner la vue en boucle). */
const POSES_MAX = 30;

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

/** T4-V1-010 — tourne le cap AUTOUR de `pivot` : le point du sol garde sa place à l'écran (la caméra glisse d'autant). Sans
 *  pivot ou sans projection : le cap seul, autour du centre de la caméra (comportement d'avant). */
function tournerAutour(map: CartePresentable, cap: number, pivot: [number, number] | null): void {
  const { project, unproject, getCenter, jumpTo } = map as CartePresentable & { jumpTo?: (o: { center: [number, number] }) => unknown };
  const centre = getCenter?.call(map);
  if (!pivot || !project || !unproject || !centre || !jumpTo) { map.setBearing!(cap); return; }
  const avant = project.call(map, pivot);
  map.setBearing!(cap);
  const apres = project.call(map, pivot);
  // Le point du centre de la caméra (padding compris) décalé de ce dont le pivot a bougé : il redevient le centre.
  const c = project.call(map, [centre.lng, centre.lat]);
  const nouveau = unproject.call(map, [c.x + apres.x - avant.x, c.y + apres.y - avant.y]);
  jumpTo.call(map, { center: [nouveau.lng, nouveau.lat] });
}

/** UN doigt (ou le bouton principal) fait tourner la maison ; deux doigts restent à la carte (pincer). T4-V1-010 —
 *  autour du centre de la maison (`pivot`) quand l'hôte le donne. */
function tournerUnDoigt(map: CartePresentable, surGeste: () => void, pivot?: () => [number, number] | null): () => void {
  const el = map.getCanvasContainer?.();
  if (!el || !map.setBearing || !map.getBearing) return () => {};
  const doigts = new Set<number>();
  let depart: { x: number; cap: number; pivot: [number, number] | null } | null = null;
  const bas = (ev: PointerEvent) => {
    surGeste();
    doigts.add(ev.pointerId);
    try { el.setPointerCapture?.(ev.pointerId); } catch { /* pointeur déjà relâché */ }
    depart = doigts.size === 1 && ev.button === 0 ? { x: ev.clientX, cap: map.getBearing!(), pivot: pivot?.() ?? null } : null;
  };
  const bouge = (ev: PointerEvent) => { if (depart && doigts.has(ev.pointerId)) tournerAutour(map, depart.cap - (ev.clientX - depart.x) * DEG_PAR_PX, depart.pivot); };
  const haut = (ev: PointerEvent) => { doigts.delete(ev.pointerId); depart = null; };
  el.addEventListener('pointerdown', bas);
  el.addEventListener('pointermove', bouge);
  for (const t of ['pointerup', 'pointercancel'] as const) el.addEventListener(t, haut);
  el.addEventListener('wheel', surGeste);
  map.dragPan?.disable();
  return () => {
    el.removeEventListener('pointerdown', bas);
    el.removeEventListener('pointermove', bouge);
    for (const t of ['pointerup', 'pointercancel'] as const) el.removeEventListener(t, haut);
    el.removeEventListener('wheel', surGeste);
    map.dragPan?.enable();
  };
}

/** La toile de la carte, montrée au client : nommée en français, hors de l'ordre de tabulation (elle se tourne au
 *  doigt, pas au clavier). Rend les attributs d'avant à la sortie. */
function nommerToile(map: CartePresentable): () => void {
  const toile = map.getCanvas?.();
  if (!toile?.setAttribute) return () => {};
  const noms = ['aria-label', 'role', 'tabindex', 'aria-roledescription'] as const;
  const avant = noms.map((n) => toile.getAttribute(n));
  toile.setAttribute('aria-label', 'Vue 3D de la maison');
  toile.setAttribute('role', 'img');
  toile.setAttribute('tabindex', '-1');
  toile.removeAttribute('aria-roledescription');
  return () => noms.forEach((n, i) => {
    const v = avant[i];
    if (v === null) toile.removeAttribute(n); else toile.setAttribute(n, v);
  });
}

/** La caméra en cinq nombres (centre, zoom, pente, cap), ou `null` si la carte ne la donne pas. */
function camera(map: CartePresentable): number[] | null {
  const c = map.getCenter?.();
  if (!c || !map.getZoom || !map.getPitch || !map.getBearing) return null;
  return [c.lng, c.lat, map.getZoom(), map.getPitch(), map.getBearing()];
}
const TOLERANCES = [1e-7, 1e-7, 0.01, 0.5, 0.5];
const memeCamera = (a: number[], b: number[]) => a.every((v, i) => Math.abs(v - b[i]) <= TOLERANCES[i]);

/** Tient la vue : à chaque repos de la carte (sans geste de l'utilisateur), si la caméra n'est plus celle posée —
 *  un atterrissage ou un recalage du constructeur l'a déplacée — la vue et le cadrage sont reposés. */
function tenirVue(map: CartePresentable, e: Etat, vue: VueTenue): { geste: () => void; fin: () => void } {
  let touche = false;
  let poses = 0;
  let cadree = false;
  let prete = false;
  let posee: number[] | null = null;
  let minuteur: ReturnType<typeof setTimeout> | null = null;
  const poser = () => {
    if (poses >= POSES_MAX) return;
    poses += 1;
    posee = null;
    cadree = vue.poser() || cadree;
  };
  const verifier = () => {
    minuteur = null;
    if (!e.actif || touche || map.isMoving?.()) return;
    const cam = camera(map);
    if (!vue.atteinte() || (posee && cam && !memeCamera(cam, posee))) { poser(); return; }
    // Vue atteinte mais toit pas encore cadré (pans inconnus avant l'hydratation) : le cadrage seul, sans animation ;
    // l'atterrissage de l'hydratation déplacera la caméra, et la vue sera reposée à ce repos-là.
    if (!cadree) { cadree = vue.cadrer(); return; }
    if (!posee) posee = cam;
    if (!prete) { prete = true; vue.surPrete?.(); }
  };
  // Après la pile d'événements en cours (un `moveend` peut en déclencher un autre, et le cadrage s'y accroche).
  const plusTard = () => { if (minuteur === null) minuteur = setTimeout(verifier, 0); };
  map.on?.('moveend', plusTard);
  map.on?.('idle', plusTard);
  poser();
  plusTard();
  return {
    geste: () => { touche = true; },
    fin: () => {
      map.off?.('moveend', plusTard);
      map.off?.('idle', plusTard);
      if (minuteur !== null) clearTimeout(minuteur);
      map.setPadding?.({ top: 0, bottom: 0, left: 0, right: 0 }); // le ciel gardé de la vue client ne la suit pas
    },
  };
}

/** Entre (vrai) ou sort (faux) du mode présentation ; rend l'état posé. Idempotent. J1 — `vue` : la vue tenue. */
export function poserPresentation(map: CartePresentable, actif: boolean, vue?: VueTenue): boolean {
  const e = etatDe(map);
  if (e.actif === actif) return actif;
  e.actif = actif;
  const veiller = () => { if (e.actif) taire(map, e); };
  if (actif) {
    taire(map, e);
    map.on?.('idle', veiller);
    const tenue = vue ? tenirVue(map, e, vue) : null;
    const finRotation = tournerUnDoigt(map, () => tenue?.geste(), vue?.pivot);
    const finToile = nommerToile(map);
    e.quitter = () => { map.off?.('idle', veiller); finRotation(); finToile(); tenue?.fin(); };
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

/** Suites des écrans v2 (24/11) — l'ÉTAPE guidée que l'hôte (coque de l'atelier ERP) montre : la carte dessine ce que la
 *  maquette de cette étape dessine — cotes, contour or et coins au Toit (`Main`), chaînes et onduleur à l'Électrique
 *  (`Electrique`). `null` (site public, mode Expert, vue client) : tout comme avant. Affichage seul, rien n'est écrit. */
export type EtapeAtelier = 'toit' | 'panneaux' | 'electrique' | 'resultats' | 'documents';
const etapes = new WeakMap<object, { etape: EtapeAtelier | null; ecouteurs: Set<() => void> }>();
const etapeDe = (map: object) => {
  let e = etapes.get(map);
  if (!e) { e = { etape: null, ecouteurs: new Set() }; etapes.set(map, e); }
  return e;
};

/** Vrai quand l'étape montrée est `etape`, ou qu'aucune étape n'est déclarée. */
export const montreALEtape = (map: object, etape: EtapeAtelier): boolean => [null, etape].includes(etapes.get(map)?.etape ?? null);

/** Un calque ou un module de scène se ré-applique à chaque changement d'étape. */
export function surEtape(map: object, fn: () => void): void { etapeDe(map).ecouteurs.add(fn); }

/** L'hôte déclare l'étape montrée (`null` : aucune) ; idempotent. */
export function poserEtapeAtelier(map: CartePresentable, etape: EtapeAtelier | null): void {
  const e = etapeDe(map);
  if (e.etape === etape) return;
  e.etape = etape;
  e.ecouteurs.forEach((fn) => fn());
  map.triggerRepaint?.();
}
