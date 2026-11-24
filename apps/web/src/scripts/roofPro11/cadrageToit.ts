// F6 (maquettes 22/11) — « le toit remplit la carte » : l'écran hôte (atelier ERP) demande UN
// cadrage de la caméra sur TOUS les pans (ouverture d'un calepinage enregistré, retour de la
// carte après une étape pleine). La caméra seule bouge : aucune géométrie, aucun calcul, aucun
// brouillon — la scène n'est jamais marquée modifiée (la caméra n'est pas sérialisée).
// Le site public ne l'appelle pas ; sans `zoomMax`, le plafond reste celui d'aujourd'hui (19).
import { WGS84_RADIUS } from '../../lib/geo';
import { cadrageAnneaux, type LngLat, type OptionsCadrage as OptionsCadrageToit } from '../../lib/roof';
import { appliquerVue, cibleVue, type NomVue } from './vuesCamera';
import { poserEtapeAtelier, poserPresentation, type CartePresentable, type EtapeAtelier } from './presentationCarte';

/** H1 (tour 3) — `basPx` : hauteur du bas de la carte COUVERTE (tiroir de la tablette) ; le toit est cadré au centre
 *  de la partie VISIBLE, au-dessus. Absent ou 0 : la carte entière, comportement d'avant. */
export interface OptionsCadrage extends OptionsCadrageToit {
  basPx?: number;
  /** J1 (tour 4) — vue client : pixels du HAUT de la carte laissés au ciel (marge haute de la caméra) ; la maison se
   *  pose plus bas, comme sur la maquette, en vue inclinée aussi. Absent : aucune marge (comportement d'avant). */
  cielPx?: number;
  /** Demande croisée (coque v2) — pixels de la carte COUVERTS par les pièces flottantes (barre du projet en haut, rail à
   *  gauche, inspecteur à droite, outils en bas) : le toit est cadré et centré dans la zone LIBRE ; `bas` remplace alors
   *  `basPx`. Absent (site public) : comportement d'avant. */
  margesPx?: { haut: number; gauche: number; droite: number; bas: number };
}

/** Le centre de la carte qui place `centre` au milieu de la zone visible, décalée de (`dxPx`, `dyPx`) pixels (vers l'est,
 *  vers le bas) du centre de la carte. Vue du dessus, cap nul (mètres par pixel de MapLibre, tuiles 512 px). */
function centreDecale(centre: LngLat, zoom: number, dxPx: number, dyPx: number): LngLat {
  const lat = centre[1];
  const metresParPixel = (2 * Math.PI * WGS84_RADIUS * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** zoom);
  const degres = (px: number, cos = 1) => (px * metresParPixel) / ((Math.PI / 180) * WGS84_RADIUS * cos);
  return [centre[0] - degres(dxPx, Math.cos((lat * Math.PI) / 180)), lat + degres(dyPx)];
}

export { appliquerVue };

export interface CarteCadrable {
  resize(): unknown;
  jumpTo(o: { center?: LngLat; zoom?: number; pitch?: number; bearing?: number;
    padding?: { top: number; bottom: number; left: number; right: number } }): unknown;
  easeTo(o: { pitch: number; bearing: number; duration: number; essential?: boolean }): unknown;
  isMoving(): boolean;
  once(type: string, fn: () => void): unknown;
  on(type: string, fn: (e: { originalEvent?: unknown }) => void): unknown;
  off(type: string, fn: (e: { originalEvent?: unknown }) => void): unknown;
  getContainer(): { clientWidth: number; clientHeight: number };
  /** ACAL1839 — lecture de la caméra posée, pour cadrer le VOLUME (murs compris) en vue inclinée. */
  project?(ll: LngLat): { x: number; y: number };
  unproject?(p: [number, number]): { lng: number; lat: number };
  getPitch?(): number;
  getZoom?(): number;
}

/** Ce que le constructeur lit au moment de l'appel (état vivant de la scène). */
export interface SourcesCamera {
  anneaux: () => readonly LngLat[][];
  azimut: () => number;
  /** Vrai pendant un tracé : jamais de cadrage sous la main de l'utilisateur. */
  trace: () => boolean;
  /** ACAL1839 — sommets du VOLUME de la maison `[lng, lat, hauteur m]` (dalle de chaque sommet de pan, haut des
   *  obstacles) ; absent ou vide : le contour seul (d'avant). */
  volume?: () => readonly (readonly [number, number, number])[];
}

/** ACAL1839 — la part de la zone libre (largeur ET hauteur) que le volume occupe au plus : l'air autour de la maison ; sans
 *  `part` demandée (atelier), un peu moins, ses cartes flottantes n'étant pas toutes comptées dans ses marges. */
const PART_VOLUME_MAX = 0.8;
const PART_VOLUME_ATELIER = 0.72;
const M_PAR_DEG = (Math.PI / 180) * WGS84_RADIUS;

/**
 * ACAL1839 — en vue INCLINÉE, le cadrage du contour au sol coupait les murs (maison de 6 m : un mur qui remplit l'écran).
 * Le volume entier — chaque sommet au sol et à sa hauteur — est projeté par la caméra posée, puis zoom et centre
 * sont corrigés (4 passes, la perspective change avec le zoom) pour qu'il tienne dans la zone libre, centré, à au plus
 * `part` de sa largeur et de sa hauteur. Caméra seule ; faux si la carte ne sait pas projeter.
 */
function cadrerVolume(map: CarteCadrable, sommets: readonly (readonly [number, number, number])[], libre: { x0: number; y0: number; x1: number; y1: number }, part: number, zoomMax: number): boolean {
  const { project, unproject, getZoom, getPitch } = map;
  if (!project || !unproject || !getZoom || !getPitch || sommets.length === 0) return false;
  const cos = Math.cos((sommets[0][1] * Math.PI) / 180);
  for (let passe = 0; passe < 4; passe++) {
    // En CHAQUE sommet (la perspective grossit ce qui est près de l'œil, et l'angle du rayon y diffère de la pente) : le sol
    // s'y projette par une application linéaire M (1 m est, 1 m nord) de valeurs singulières s (en travers du rayon) et
    // s·cos θ (le long) ; 1 m vertical y monte de s·sin θ = (‖M‖² ² − 4·det²)^¼.
    const pts = sommets.flatMap(([lng, lat, z]) => {
      const p = project.call(map, [lng, lat]);
      const e = project.call(map, [lng + 1 / (M_PAR_DEG * cos), lat]);
      const n = project.call(map, [lng, lat + 1 / M_PAR_DEG]);
      const [ex, ey, nx, ny] = [e.x - p.x, e.y - p.y, n.x - p.x, n.y - p.y];
      const f2 = ex * ex + ey * ey + nx * nx + ny * ny;
      const det = ex * ny - ey * nx;
      return [p, { x: p.x, y: p.y - z * Math.pow(Math.max(0, f2 * f2 - 4 * det * det), 0.25) }];
    });
    const [x0, x1] = [Math.min(...pts.map((p) => p.x)), Math.max(...pts.map((p) => p.x))];
    const [y0, y1] = [Math.min(...pts.map((p) => p.y)), Math.max(...pts.map((p) => p.y))];
    const f = Math.min((part * (libre.x1 - libre.x0)) / Math.max(1, x1 - x0), (part * (libre.y1 - libre.y0)) / Math.max(1, y1 - y0));
    const { clientWidth: w, clientHeight: h } = map.getContainer();
    const c = unproject.call(map, [w / 2 + (x0 + x1) / 2 - (libre.x0 + libre.x1) / 2, h / 2 + (y0 + y1) / 2 - (libre.y0 + libre.y1) / 2]);
    map.jumpTo({ center: [c.lng, c.lat], zoom: Math.min(zoomMax, getZoom.call(map) + Math.log2(f)) });
  }
  return true;
}

/**
 * Pose la caméra (centre + zoom, pente et cap GARDÉS : Plan reste Plan, 3D reste 3D) sur tous
 * les pans, sans animation. Si la caméra bouge encore (atterrissage du boot), le cadrage attend
 * la fin du mouvement ; il est re-posé une fois au prochain `idle` (redimensionnement tardif),
 * sauf si l'utilisateur a touché la carte entre-temps. Faux = rien à cadrer (aucun pan, tracé).
 */
export function cadrerToit(map: CarteCadrable, sources: SourcesCamera, options: OptionsCadrage = {}): boolean {
  if (sources.trace()) return false;
  let touche = false;
  const geste = (e: { originalEvent?: unknown }) => { if (e?.originalEvent) touche = true; };
  const poser = (): boolean => {
    if (touche || sources.trace()) return false;
    map.resize();
    const { clientWidth, clientHeight } = map.getContainer();
    const borne = (px: number | undefined, total: number) => Math.max(0, Math.min(px ?? 0, total * 0.6));
    const m = options.margesPx;
    const [haut, gauche, droite] = m ? [borne(m.haut, clientHeight), borne(m.gauche, clientWidth), borne(m.droite, clientWidth)] : [0, 0, 0];
    const bas = borne(m ? m.bas : options.basPx, clientHeight);
    const cible = cadrageAnneaux(sources.anneaux(), Math.max(1, clientWidth - gauche - droite), Math.max(1, clientHeight - haut - bas), options);
    if (!cible) return false;
    const ciel = Math.max(0, Math.min(options.cielPx ?? 0, clientHeight * 0.6));
    const [dx, dy] = [(gauche - droite) / 2, (haut - bas) / 2];
    const pose = dx !== 0 || dy !== 0 ? { ...cible, center: centreDecale(cible.center, cible.zoom, dx, dy) } : cible;
    const volume = sources.volume?.() ?? [];
    if (volume.length >= 3 && (map.getPitch?.() ?? 0) > 1 && map.project) { // ACAL1839 — vue inclinée : le volume entier, avec de l'air
      map.jumpTo({ ...pose, padding: { top: 0, bottom: 0, left: 0, right: 0 } });
      const libre = { x0: gauche, y0: Math.max(haut, ciel), x1: clientWidth - droite, y1: clientHeight - bas };
      if (cadrerVolume(map, volume, libre, Math.min(PART_VOLUME_MAX, options.part ?? PART_VOLUME_ATELIER), options.zoomMax ?? 19)) return true;
    }
    map.jumpTo(ciel > 0 ? { ...pose, padding: { top: ciel, bottom: 0, left: 0, right: 0 } } : pose);
    return true;
  };
  const anneauxValides = sources.anneaux().some((a) => Array.isArray(a) && a.length >= 3);
  if (!anneauxValides) return false;
  map.on('movestart', geste);
  map.once('idle', () => { poser(); map.off('movestart', geste); });
  if (map.isMoving()) map.once('moveend', () => { poser(); });
  else poser();
  return true;
}

/** J1 — la vue que la présentation TIENT (`modePresentation(true, { vue, cadrage, surPrete })`). */
export interface VueClient { vue: NomVue; cadrage?: OptionsCadrage; surPrete?: () => void }

const ecartAngle = (a: number, b: number) => Math.abs(((((a - b) % 360) + 540) % 360) - 180);

/** Les commandes de caméra de l'API du constructeur (ACAL435 + F6) ; H6 — `modePresentation` (vue client) ; J1 — la vue
 *  client TENUE : posée à l'entrée, reposée après tout mouvement qui n'est pas un geste de l'utilisateur. */
export function apiCamera(map: CarteCadrable & CartePresentable, sources: SourcesCamera, reducedMotion: boolean) {
  const tenue = (v: VueClient) => ({
    poser: () => { appliquerVue(map, v.vue, sources.azimut(), reducedMotion); return cadrerToit(map, sources, v.cadrage); },
    cadrer: () => cadrerToit(map, sources, v.cadrage),
    atteinte: () => {
      if (!map.getPitch || !map.getBearing) return true;
      const cible = cibleVue(v.vue, sources.azimut());
      return Math.abs(map.getPitch() - cible.pitch) <= 0.5 && ecartAngle(map.getBearing(), cible.bearing) <= 0.5;
    },
    surPrete: v.surPrete,
  });
  // ACAL1839 — changer de vue (Plan ↔ 3D) recadre le VOLUME avec le dernier cadrage demandé par l'hôte : en 3D la maison
  // entière (murs compris) reste visible, jamais coupée sous les pièces flottantes de l'atelier.
  let dernier: OptionsCadrage | null = null;
  return {
    appliquerVue: (nom: NomVue) => { appliquerVue(map, nom, sources.azimut(), reducedMotion); if (dernier) cadrerToit(map, sources, dernier); },
    cadrerToit: (options?: OptionsCadrage) => cadrerToit(map, sources, (dernier = options ?? {})),
    modePresentation: (actif: boolean, vue?: VueClient) => poserPresentation(map, actif, vue ? tenue(vue) : undefined),
    /** Suites v2 — l'étape guidée montrée par la coque (`null` : Expert, vue client) : chaque repère à l'étape de sa maquette. */
    etapeAtelier: (etape: EtapeAtelier | null) => poserEtapeAtelier(map, etape),
  };
}
