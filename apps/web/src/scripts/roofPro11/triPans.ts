/**
 * ACAL728 — tri d'AFFICHAGE de la liste des pans par accès solaire moyen décroissant.
 * Jamais écrit dans le document. L'accès d'un pan est la moyenne de ses valeurs NON NULLES
 * (`geometrieEnregistree.solarAccess.values`) ; un pan sans valeur est « non calculé » et
 * passe en dernier — jamais compté pour 0.
 */
import { type AreaRecord } from './types';

/** Moyenne (0..1) des valeurs non nulles enregistrées du pan ; `null` si aucune. */
export function accesMoyenDuPan(a: Pick<AreaRecord, 'geometrieEnregistree'>): number | null {
  const vals = (a.geometrieEnregistree?.solarAccess?.values ?? []).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
  return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
}

/** Copie triée (stable) : accès décroissant, « non calculé » en dernier. `vivant` donne
 *  l'accès du calcul vivant d'un pan (le pan actif), sinon l'enregistré. */
export function trierPansParAcces<T extends Pick<AreaRecord, 'geometrieEnregistree'>>(
  areas: readonly T[],
  vivant?: (a: T) => number | null | undefined,
): T[] {
  const acces = (a: T) => vivant?.(a) ?? accesMoyenDuPan(a);
  return areas
    .map((a, i) => ({ a, i, v: acces(a) }))
    .sort((x, y) => (x.v === null ? 1 : 0) - (y.v === null ? 1 : 0) || (y.v ?? 0) - (x.v ?? 0) || x.i - y.i)
    .map((e) => e.a);
}

/** « accès solaire 91 % » ou « non calculé ». */
export const mentionAcces = (v: number | null | undefined): string =>
  typeof v === 'number' ? `accès solaire ${Math.round(v * 100)} %` : 'non calculé';
