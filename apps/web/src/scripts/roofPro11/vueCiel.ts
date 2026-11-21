/**
 * ACAL460 — FACTEUR DE VUE DU CIEL D'UN PAN : la part du ciel DIFFUS (supposé isotrope) que les
 * obstructions laissent voir à ses modules. Écrit en `zones[].geometry.skyViewFactor`
 * (contrat `calepinage_table_ombrage.json`, ACAL389), lu côté serveur par ACAL461.
 *
 * Intégrale sur le demi-ciel visible du plan (direction de hauteur a, d'azimut φ) : poids =
 * cos(angle à la normale) × cos(a) da dφ ; une direction coupée par le prédicat (`isSunBlocked`
 * par défaut) compte 0. Facteur = Σ poids libres ÷ Σ poids du ciel du plan, moyenné sur les modules.
 * Dérivation à la main : plan horizontal, ciel coupé sous la hauteur h, poids = sin a cos a ⇒
 * ∫ de h à 90° ÷ ∫ de 0 à 90° = cos²h. Plan sans obstruction ⇒ 1.
 * `horizon: false` comme `solarAccess.method` : l'horizon lointain reste le poste séparé de la chaîne.
 * PUR : aucun DOM.
 *
 * PAS — mesuré le 21/11 (plan horizontal, ciel coupé sous h = 0,5°…80° par pas de 0,5°, quadrature au
 * point milieu, écart maximal à cos²h) : pas de hauteur 2,5° → 1,745 point ; 3° → 2,62 (dépasse) ;
 * 4° → 3,43 ; 2° → 1,748. L'azimut ne change rien à l'écart (horizon isotrope) : 15° garde la
 * résolution des obstructions étroites.
 */
import { isSunBlocked, type ShadeObstructionENU } from '../../lib/shadingEngine';

/** Pas d'intégration (°) : le plus gros dont l'écart à cos²(h) reste sous 2 points (seuil d'ACAL381). */
export const PAS_HAUTEUR_DEG = 2.5;
export const PAS_AZIMUT_DEG = 15;

export interface FacteurVueCiel {
  facteur: number;
  methode: { diffus: 'isotrope'; horizon: false; resolution: 'centres_de_modules' };
  signature: string;
}

export type Bloque = (x: number, y: number, hauteurDeg: number, azimutDeg: number) => boolean;
const RAD = Math.PI / 180;

/** Facteur d'UN point (module) : `pente` = inclinaison du plan (°), `azimut` = sa face (boussole, 180 = sud). */
function facteurPoint(x: number, y: number, pente: number, azimut: number, bloque: Bloque, pas: { h: number; az: number }): number {
  const nx = Math.sin(pente * RAD) * Math.sin(azimut * RAD);
  const ny = Math.sin(pente * RAD) * Math.cos(azimut * RAD);
  const nz = Math.cos(pente * RAD);
  let libre = 0;
  let total = 0;
  for (let h = pas.h / 2; h < 90; h += pas.h) {
    for (let az = pas.az / 2; az < 360; az += pas.az) {
      const ca = Math.cos(h * RAD);
      const cosT = ca * Math.sin(az * RAD) * nx + ca * Math.cos(az * RAD) * ny + Math.sin(h * RAD) * nz;
      if (cosT <= 0) continue; // derrière le plan : pas son ciel
      const w = cosT * ca;
      total += w;
      if (!bloque(x, y, h, az)) libre += w;
    }
  }
  return total > 0 ? libre / total : 1;
}

/** Facteur du pan (moyenne des modules), ou `null` sans module ou sans obstruction (jamais « 1 » écrit). */
export function facteurVueCiel(
  panneaux: readonly { x: number; y: number }[],
  obstructions: readonly ShadeObstructionENU[],
  pente: number,
  azimut: number,
  bloque: Bloque = (x, y, h, az) => isSunBlocked(x, y, obstructions, h, az),
  pas: { h: number; az: number } = { h: PAS_HAUTEUR_DEG, az: PAS_AZIMUT_DEG },
): number | null {
  if (!panneaux.length || !obstructions.length) return null;
  const somme = panneaux.reduce((s, p) => s + facteurPoint(p.x, p.y, pente, azimut, bloque, pas), 0);
  return Math.round((somme / panneaux.length) * 1e4) / 1e4;
}

/** Le bloc à ranger au document, ou `null`. */
export function vueCielDuPan(f: number | null, signature: string): FacteurVueCiel | null {
  return f === null ? null : { facteur: f, methode: { diffus: 'isotrope', horizon: false, resolution: 'centres_de_modules' }, signature };
}

/** La part de `SerializeMeta` (prefill.ts) que lit ce module : la vue du ciel PAR ZONE et la signature courante. */
export interface MetaVueCiel {
  skyViewByZone?: Record<string, FacteurVueCiel | null | undefined>;
  signatureOmbrage?: string;
}

/** Écrit la vue du ciel du pan actif `id` dans sa géométrie (absente = clé absente). */
export function ajouterVueCiel(g: object | undefined, meta: MetaVueCiel | undefined, id: string): void {
  const v = meta?.skyViewByZone?.[id];
  if (g && v) (g as { skyViewFactor?: FacteurVueCiel }).skyViewFactor = JSON.parse(JSON.stringify(v)) as FacteurVueCiel;
}

/** Pan non actif : la valeur RELUE n'est gardée que si les sources d'ombrage n'ont pas bougé. */
export function garderVueCielRelue(g: object | undefined, meta: MetaVueCiel | undefined): void {
  const lu = g as { skyViewFactor?: FacteurVueCiel } | undefined;
  if (lu?.skyViewFactor && lu.skyViewFactor.signature !== meta?.signatureOmbrage) delete lu.skyViewFactor;
}
