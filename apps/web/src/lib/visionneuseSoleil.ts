/**
 * LOT 6 (D-ACAL-132 à 138) — lecture STRICTE de la clé additive `visionneuse_soleil` de la page client
 * (contrat `src/contract_samples/visionneuse_soleil.json`), libellé de l'instant et bornes de carte.
 *
 * PUR (aucun DOM, aucun Three, aucun MapLibre). Une clé absente ou malformée → `null`, jamais un throw,
 * jamais une valeur devinée : la page garde alors exactement la visionneuse d'aujourd'hui. Un pan dont l'id
 * ou le nombre de valeurs ne correspond pas au `roof_layout` lu est écarté en bloc (jamais réaligné) ; une
 * valeur d'accès hors [0 ; 1] écarte son pan (jamais bornée en silence). Les valeurs sont celles ENREGISTRÉES
 * par le calepinage : rien n'est recalculé ici.
 */
import { couleurAccesActive } from './shadingEngine';
import { DEG2M_GEO } from './geo';
import type { RoofLayout } from './proposition';
import type { EnvironmentObject, EnvironmentKind } from '../scripts/roofPro11/environment';

export interface ZoneAccesSoleil {
  /** Position du pan dans `roof_layout.zones` lu. */
  index: number;
  id: string;
  /** Un facteur 0-1 par module, dans l'ordre de `geometry.panels` ; `null` = non calculé (non teinté). */
  acces: Array<number | null>;
}

export interface InstantSoleil {
  jour: number;
  heure: number;
}

export interface VisionneuseSoleil {
  zones: ZoneAccesSoleil[];
  environnement: EnvironmentObject[];
  /** Instant d'ouverture : celui choisi par le commercial, sinon l'été à midi (D-ACAL-135). */
  ouverture: InstantSoleil;
}

/** Raccourcis de saison de l'atelier (année de dessin 2028 : 355 = 20 décembre, 172 = 20 juin). */
export const JOUR_HIVER = 355;
export const JOUR_ETE = 172;
const OUVERTURE_DEFAUT: InstantSoleil = { jour: JOUR_ETE, heure: 12 };
const GENRES: readonly EnvironmentKind[] = ['arbre', 'batiment', 'poteau', 'ligne'];
const NOMBRES = ['crownDiameterM', 'lengthM', 'widthM', 'diameterM', 'epaisseurM'] as const;

const estObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const fini = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

function lireTrace(v: unknown): Array<[number, number]> | null {
  if (!Array.isArray(v) || v.length < 2) return null;
  const pts = v.filter((p): p is [number, number] => Array.isArray(p) && p.length === 2 && fini(p[0]) && fini(p[1]));
  return pts.length === v.length ? pts.map(([lng, lat]) => [lng, lat]) : null;
}

/** Une zone servie, vérifiée contre le layout lu (id ET longueur), sinon `null`. */
function lireZone(z: unknown, layout: RoofLayout): ZoneAccesSoleil | null {
  if (!estObj(z) || !Number.isInteger(z.index) || typeof z.id !== 'string' || !Array.isArray(z.acces)) return null;
  const pan = layout.zones[z.index as number];
  if (!pan || pan.id !== z.id || !pan.geometry || pan.geometry.panels.length !== z.acces.length) return null;
  const acces: Array<number | null> = [];
  for (const a of z.acces) {
    if (a === null) acces.push(null);
    else if (fini(a) && a >= 0 && a <= 1) acces.push(a);
    else return null;
  }
  return acces.some((a) => a !== null) ? { index: z.index as number, id: z.id, acces } : null;
}

/** Un objet voisin : géométrie de la liste blanche seule (jamais `label`, `id` synthétique). */
function lireVoisin(o: unknown, i: number): EnvironmentObject | null {
  if (!estObj(o) || !GENRES.includes(o.kind as EnvironmentKind) || o.supposeCoupe === true) return null;
  if (!fini(o.centerLng) || !fini(o.centerLat) || !fini(o.heightM) || o.heightM <= 0) return null;
  const v: EnvironmentObject = { id: `voisin-${i}`, kind: o.kind as EnvironmentKind, centerLng: o.centerLng, centerLat: o.centerLat, heightM: o.heightM };
  for (const k of NOMBRES) if (fini(o[k]) && (o[k] as number) > 0) v[k] = o[k] as number;
  if (typeof o.evergreen === 'boolean') v.evergreen = o.evergreen;
  const footprint = lireTrace(o.footprint);
  if (footprint) v.footprint = footprint;
  const trace = lireTrace(o.trace);
  if (trace) v.trace = trace;
  return v;
}

function lireInstant(v: unknown): InstantSoleil | null {
  if (!estObj(v) || !Number.isInteger(v.jour) || !fini(v.heure)) return null;
  const jour = v.jour as number;
  return jour >= 1 && jour <= 366 && v.heure >= 0 && v.heure <= 24 ? { jour, heure: v.heure } : null;
}

/**
 * Lit `payload.visionneuse_soleil` contre le `roof_layout` lu par `parseRoofLayout`. `null` quand la clé est
 * absente, sans layout, d'une autre version, ou d'une forme qui ne tient pas le contrat (toute clé de la forme
 * est obligatoire — PACT10).
 */
export function lireVisionneuseSoleil(payload: unknown, layout: RoofLayout | null): VisionneuseSoleil | null {
  try {
    const v = estObj(payload) ? payload.visionneuse_soleil : undefined;
    if (!layout || !estObj(v) || v.version !== 1) return null;
    if (!Array.isArray(v.zones) || !Array.isArray(v.environnement) || !('instant_choisi' in v)) return null;
    if (v.instant_choisi !== null && !lireInstant(v.instant_choisi)) return null;
    const zones = v.zones.map((z) => lireZone(z, layout)).filter((z): z is ZoneAccesSoleil => z !== null);
    const environnement = v.environnement.map(lireVoisin).filter((o): o is EnvironmentObject => o !== null);
    return { zones, environnement, ouverture: lireInstant(v.instant_choisi) ?? { ...OUVERTURE_DEFAUT } };
  } catch {
    return null;
  }
}

export type LangueSoleil = 'fr' | 'en' | 'ar';
const MOIS: Record<LangueSoleil, readonly string[]> = {
  fr: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  // Jeu marocain (Bulletin officiel, locale ar-MA), comme les dates de la page.
  ar: ['يناير', 'فبراير', 'مارس', 'أبريل', 'ماي', 'يونيو', 'يوليوز', 'غشت', 'شتنبر', 'أكتوبر', 'نونبر', 'دجنبر'],
};

// L'heure de la scène est l'heure SOLAIRE (midi = soleil au plus haut), pas celle de la montre du client : chaque
// heure imprimée le dit. Aucune conversion en heure légale ici (elle demande des données que la page n'a pas).
const SOLAIRE: Record<LangueSoleil, string> = { fr: '(heure solaire)', en: '(solar time)', ar: '(بالتوقيت الشمسي)' };
const heure = (h: number, langue: LangueSoleil) =>
  langue === 'en' ? `${Math.round(h)}:00` : langue === 'ar' ? `الساعة ${Math.round(h)}` : `${Math.round(h)} h`;

/** « 20 décembre · 12 h (heure solaire) » — jour dans l'année de dessin 2028 de l'atelier (`formats.js::jourMois`). */
export function libelleInstant(jour: number, h: number, langue: LangueSoleil): string {
  const d = new Date(Date.UTC(2028, 0, Math.max(1, Math.min(366, Math.round(jour)))));
  const mois = (MOIS[langue] ?? MOIS.fr)[d.getUTCMonth()];
  return `${d.getUTCDate()} ${mois} · ${heure(h, langue)} ${SOLAIRE[langue] ?? SOLAIRE.fr}`;
}

/** « Lever 7 h · coucher 17 h (heure solaire) » — les bornes du curseur, dites une fois sous lui. */
export function libelleJournee(lever: number, coucher: number, langue: LangueSoleil): string {
  if (langue === 'en') return `Sunrise ${heure(lever, 'en')} · sunset ${heure(coucher, 'en')} ${SOLAIRE.en}`;
  if (langue === 'ar') return `الشروق ${heure(lever, 'ar')} · الغروب ${heure(coucher, 'ar')} ${SOLAIRE.ar}`;
  return `Lever ${heure(lever, 'fr')} · coucher ${heure(coucher, 'fr')} ${SOLAIRE.fr}`;
}

/** Bornes de la carte (D-ACAL-138) : emprise des sommets + `margeM` ; zoom mini = zoom initial − 2. */
export function bornesCarte(layout: RoofLayout, zoomInitial: number, margeM = 150): { bornes: [[number, number], [number, number]]; zoomMin: number } | null {
  const pts = layout.zones.flatMap((z) => z.vertices);
  if (!pts.length || !fini(zoomInitial)) return null;
  const lngs = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  const [s, n] = [Math.min(...lats), Math.max(...lats)];
  const dLat = margeM / DEG2M_GEO; // ACAL349 — la constante de projection unique (lib/geo.ts)
  const dLng = margeM / (DEG2M_GEO * Math.max(0.05, Math.cos((((s + n) / 2) * Math.PI) / 180)));
  return { bornes: [[Math.min(...lngs) - dLng, s - dLat], [Math.max(...lngs) + dLng, n + dLat]], zoomMin: Math.max(0, zoomInitial - 2) };
}

/** Le dégradé de la légende : les couleurs MÊMES que la teinte (palette « atelier »), aux arrêts de sa rampe. */
export function degradeLegende(): string {
  const arrets = [0, 0.3, 0.5, 0.72, 1].map((a) => {
    const c = couleurAccesActive(a, 'atelier');
    return `rgb(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)}) ${Math.round(a * 100)}%`;
  });
  return `linear-gradient(90deg, ${arrets.join(', ')})`;
}
