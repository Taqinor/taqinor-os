// F6 (maquettes 22/11) — « le toit remplit la carte » : l'écran hôte (atelier ERP) demande UN
// cadrage de la caméra sur TOUS les pans (ouverture d'un calepinage enregistré, retour de la
// carte après une étape pleine). La caméra seule bouge : aucune géométrie, aucun calcul, aucun
// brouillon — la scène n'est jamais marquée modifiée (la caméra n'est pas sérialisée).
// Le site public ne l'appelle pas ; sans `zoomMax`, le plafond reste celui d'aujourd'hui (19).
import { WGS84_RADIUS } from '../../lib/geo';
import { cadrageAnneaux, type LngLat, type OptionsCadrage as OptionsCadrageToit } from '../../lib/roof';
import { appliquerVue, type NomVue } from './vuesCamera';

/** H1 (tour 3) — `basPx` : hauteur du bas de la carte COUVERTE (tiroir de la tablette) ; le toit est cadré au centre
 *  de la partie VISIBLE, au-dessus. Absent ou 0 : la carte entière, comportement d'avant. */
export interface OptionsCadrage extends OptionsCadrageToit {
  basPx?: number;
}

/** Le centre de la carte qui place `centre` au milieu de la partie visible (le bas couvert sur `basPx`). Vue du dessus,
 *  cap nul : le centre de la carte descend de `basPx / 2` pixels (mètres par pixel de MapLibre, tuiles 512 px). */
function centreAuDessus(centre: LngLat, zoom: number, basPx: number): LngLat {
  const lat = centre[1];
  const metresParPixel = (2 * Math.PI * WGS84_RADIUS * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** zoom);
  return [centre[0], lat - ((basPx / 2) * metresParPixel) / ((Math.PI / 180) * WGS84_RADIUS)];
}

export { appliquerVue };

export interface CarteCadrable {
  resize(): unknown;
  jumpTo(o: { center?: LngLat; zoom?: number; pitch?: number; bearing?: number }): unknown;
  easeTo(o: { pitch: number; bearing: number; duration: number; essential?: boolean }): unknown;
  isMoving(): boolean;
  once(type: string, fn: () => void): unknown;
  on(type: string, fn: (e: { originalEvent?: unknown }) => void): unknown;
  off(type: string, fn: (e: { originalEvent?: unknown }) => void): unknown;
  getContainer(): { clientWidth: number; clientHeight: number };
}

/** Ce que le constructeur lit au moment de l'appel (état vivant de la scène). */
export interface SourcesCamera {
  anneaux: () => readonly LngLat[][];
  azimut: () => number;
  /** Vrai pendant un tracé : jamais de cadrage sous la main de l'utilisateur. */
  trace: () => boolean;
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
    const bas = Math.max(0, Math.min(options.basPx ?? 0, clientHeight * 0.6));
    const cible = cadrageAnneaux(sources.anneaux(), clientWidth, clientHeight - bas, options);
    if (!cible) return false;
    map.jumpTo(bas > 0 ? { ...cible, center: centreAuDessus(cible.center, cible.zoom, bas) } : cible);
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

/** Les deux commandes de caméra de l'API du constructeur (ACAL435 + F6). */
export function apiCamera(map: CarteCadrable, sources: SourcesCamera, reducedMotion: boolean) {
  return {
    appliquerVue: (nom: NomVue) => appliquerVue(map, nom, sources.azimut(), reducedMotion),
    cadrerToit: (options?: OptionsCadrage) => cadrerToit(map, sources, options),
  };
}
