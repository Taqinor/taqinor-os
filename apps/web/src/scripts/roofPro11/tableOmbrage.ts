/**
 * ACAL459 — TABLE DES FACTEURS D'OMBRAGE DIRECT PAR DIRECTION DU SOLEIL (azimut × hauteur), d'un pan.
 *
 * `hourlyShadeFactors` ne rend qu'une matrice 12 × 24 d'UN point où une heure masquée vaut une part
 * diffuse fixe : direct et diffus mêlés. PVsyst publie une TABLE de facteurs par direction solaire ;
 * celle-ci en est l'équivalent au navigateur : chaque case = la part des modules POSÉS dont le rayon
 * solaire n'est PAS coupé selon `isSunBlocked` (1 = plein soleil, 0 = tous masqués). Approximation
 * dite : `methode: 'centres_de_modules'` (le centre du module décide, pas de fraction de surface).
 * Rangée en `zones[].geometry.shadeTable` (contrat `calepinage_table_ombrage.json`, ACAL389) et
 * lue par le serveur (ACAL461) et le diagramme (ACAL449). Sans obstruction : AUCUNE table (jamais
 * « 1 partout », qui se lirait vérifié). PUR : aucun DOM, aucune scène.
 *
 * PAS DE GRILLE — mesuré le 20/11 (latitude 33,6°, 24 modules, 6 scénarios d'obstruction ; matrice
 * 12 × 24 recomposée par la case la plus proche puis `annualShadeFactor`, comparée à la moyenne
 * exacte des matrices par module) : hauteur 10° (les hauteurs 20° et 30° des cas de test sont des
 * lignes) ; azimut 45° → écart maximal 1,78 point (< 2, seuil d'ACAL381) ; 30° → 0,49 ; 60° → 1,97
 * (trop près du seuil pour une obstruction non mesurée) ; 90° → 5,98 (dépasse). Hauteur 20° au pas
 * 45° : 2,02 (dépasse). Plus gros pas qui tient avec marge : 45° × 10°.
 */
import { isSunBlocked, type ShadeObstructionENU } from '../../lib/shadingEngine';

/** Pas d'azimut (°) : colonnes 0, pas, 2·pas… 360 − pas. */
export const PAS_AZIMUT_DEG = 45;
/** Pas de hauteur du soleil (°) : lignes pas, 2·pas… jusqu'à 90 − pas (le soleil est > 0 et < 90). */
export const PAS_HAUTEUR_DEG = 10;

export interface TableOmbrage {
  azimutsDeg: number[];
  hauteursDeg: number[];
  /** Lignes = hauteurs, colonnes = azimuts ; valeurs dans [0, 1], 1 = aucun ombrage. */
  facteurs: number[][];
  methode: 'centres_de_modules';
  signature: string;
}

/** Signature rangée avec la table : FNV-1a de la signature des sources d'ombrage (`shadingUi.ts`). */
export const signerSources = (sources: string): string =>
  `fnv1a-${[...sources].reduce((h, ch) => Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0, 0x811c9dc5).toString(16)}`;

const suite = (pas: number, fin: number, debut = pas): number[] => {
  const out: number[] = [];
  for (let v = debut; v < fin; v += pas) out.push(v);
  return out;
};

/** La table du pan, ou `null` sans module posé ou sans obstruction (jamais une table de 1). */
export function tableOmbrage(
  panneaux: readonly { x: number; y: number }[],
  obstructions: readonly ShadeObstructionENU[],
  signature: string,
  pas: { azimutDeg?: number; hauteurDeg?: number } = {},
): TableOmbrage | null {
  if (!panneaux.length || !obstructions.length) return null;
  const azimutsDeg = suite(pas.azimutDeg ?? PAS_AZIMUT_DEG, 360, 0);
  const hauteursDeg = suite(pas.hauteurDeg ?? PAS_HAUTEUR_DEG, 90);
  const facteurs = hauteursDeg.map((h) =>
    azimutsDeg.map((az) => {
      const masques = panneaux.filter((p) => isSunBlocked(p.x, p.y, obstructions, h, az)).length;
      return Math.round((1 - masques / panneaux.length) * 1e4) / 1e4;
    }),
  );
  return { azimutsDeg, hauteursDeg, facteurs, methode: 'centres_de_modules', signature };
}

/** Écrit la table du pan actif dans sa géométrie (absente = clé absente). */
export function ajouterTableOmbrage(geometrie: { shadeTable?: TableOmbrage } | undefined, table: TableOmbrage | null | undefined): void {
  if (geometrie && table) geometrie.shadeTable = JSON.parse(JSON.stringify(table)) as TableOmbrage;
}

/** Pan non actif : la table RELUE n'est gardée que si les sources d'ombrage n'ont pas bougé. */
export function garderTableRelue(geometrie: { shadeTable?: TableOmbrage } | undefined, signature: string | undefined): void {
  if (geometrie?.shadeTable && geometrie.shadeTable.signature !== signature) delete geometrie.shadeTable;
}

/** Matrice 12 × 24 recomposée depuis la table (case la plus proche ; part diffuse des heures masquées). */
export function recomposerMatrice(
  table: TableOmbrage,
  soleil: (mois: number, heure: number) => { elevationDeg: number; azimuthDeg: number },
  diffus: number,
): number[][] {
  const proche = (xs: number[], v: number) => xs.reduce((b, x, i) => (Math.abs(x - v) < Math.abs(xs[b] - v) ? i : b), 0);
  return Array.from({ length: 12 }, (_m, m) =>
    Array.from({ length: 24 }, (_h, h) => {
      const s = soleil(m, h);
      if (s.elevationDeg <= 0) return 1;
      const f = table.facteurs[proche(table.hauteursDeg, s.elevationDeg)][proche(table.azimutsDeg, (s.azimuthDeg + 360) % 360)];
      return f + (1 - f) * diffus;
    }),
  );
}
