/**
 * ACAL422 — CRÉER LE CONTOUR DU TOIT EN SAISISSANT LONGUEUR × LARGEUR.
 *
 * `zones.ts::redimensionnerPanActif` (CALX97) repose un pan rectangulaire DÉJÀ tracé aux cotes
 * saisies, mais rien ne CRÉAIT un contour depuis des cotes : sans clic sur la carte il n'y a
 * pas de pan. L'imagerie satellite étant inégale, tracer au doigt sur une image floue est le
 * point faible : ce module pose un rectangle aux cotes saisies, centré sur le centre de la
 * carte, côté long vers l'est-ouest tourné de l'orientation saisie, puis le contour est
 * fermé par le chemin habituel (`close`).
 *
 * Aucun champ n'est borné ni arrondi (`type="text"`, `step="any"`) ; un champ vide, non
 * numérique ou ≤ 0 est refusé en nommant le champ, rien n'est créé. La géométrie des coins
 * est `snap.ts::pointDepuisCap` (aucun calcul de coordonnées neuf).
 */
import type { LngLat } from '../../lib/roof';
import { pointDepuisCap } from './snap';

export type VerdictCotes =
  | { ok: true; longueurM: number; largeurM: number; orientationDeg: number }
  | { ok: false; motif: string };

/** Lit les trois champs : refus nommé (jamais de borne ni d'arrondi). L'orientation vide vaut 0. */
export function lireCotes(longueur: string, largeur: string, orientation: string): VerdictCotes {
  const nombre = (brut: string): number => {
    const t = String(brut).trim().replace(',', '.');
    return t === '' ? NaN : Number(t);
  };
  const l = nombre(longueur);
  if (!Number.isFinite(l) || l <= 0) return { ok: false, motif: 'Longueur : saisissez un nombre de mètres supérieur à 0.' };
  const w = nombre(largeur);
  if (!Number.isFinite(w) || w <= 0) return { ok: false, motif: 'Largeur : saisissez un nombre de mètres supérieur à 0.' };
  const o = String(orientation).trim() === '' ? 0 : nombre(orientation);
  if (!Number.isFinite(o)) return { ok: false, motif: 'Orientation : saisissez un angle en degrés (nombre).' };
  return { ok: true, longueurM: l, largeurM: w, orientationDeg: o };
}

/**
 * Les 4 sommets d'un rectangle `longueurM` × `largeurM` centré sur `centre`. Orientation 0 :
 * le côté long (1ᵉʳ côté) va vers l'est ; l'orientation saisie le tourne dans le sens horaire.
 */
export function rectangleDepuisCotes(centre: LngLat, longueurM: number, largeurM: number, orientationDeg: number): LngLat[] {
  const cap = 90 + orientationDeg;
  const ouest = pointDepuisCap(centre, cap + 180, longueurM / 2);
  const est = pointDepuisCap(centre, cap, longueurM / 2);
  return [
    pointDepuisCap(ouest, cap - 90, largeurM / 2),
    pointDepuisCap(est, cap - 90, largeurM / 2),
    pointDepuisCap(est, cap + 90, largeurM / 2),
    pointDepuisCap(ouest, cap + 90, largeurM / 2),
  ];
}

export interface ToitParCotesDeps {
  /** Le bouton « + Ajouter une zone » : les champs se posent juste après. */
  ancre: HTMLElement | null;
  /** Centre de la carte (lng, lat), null si la carte n'en a pas. */
  centre: () => LngLat | null;
  /** Aucun tracé en cours ni contour fermé sur le pan actif. */
  vide: () => boolean;
  /** Pose les sommets et ferme le contour par le chemin du double-clic (`close`). */
  creer: (anneau: LngLat[]) => void;
  setStatus: (msg: string) => void;
}

/** Monte les 3 champs et « Créer le toit » ; `rafraichir` les montre tant qu'aucun contour n'existe. */
export function monterToitParCotes(deps: ToitParCotesDeps): {
  rafraichir: () => void;
  creerDepuisSaisie: (longueur: string, largeur: string, orientation: string) => boolean;
} {
  const creerDepuisSaisie = (longueur: string, largeur: string, orientation: string): boolean => {
    const refus = (motif: string): false => {
      deps.setStatus(motif);
      return false;
    };
    if (!deps.vide()) return refus('Créer le toit : effacez d’abord le tracé en cours.');
    const v = lireCotes(longueur, largeur, orientation);
    if (!v.ok) return refus(v.motif);
    const centre = deps.centre();
    if (!centre) return refus('Créer le toit : la carte n’a pas encore de centre.');
    deps.creer(rectangleDepuisCotes(centre, v.longueurM, v.largeurM, v.orientationDeg));
    deps.setStatus(`Toit créé : ${v.longueurM} × ${v.largeurM} m.`);
    return true;
  };
  const ancre = deps.ancre;
  if (!ancre || typeof document === 'undefined' || !ancre.parentElement) return { rafraichir: () => {}, creerDepuisSaisie };
  const rangee = document.createElement('form');
  rangee.id = 'rp9-toit-cotes';
  rangee.noValidate = true;
  rangee.className = 'mt-2 flex flex-wrap items-center gap-1';
  rangee.setAttribute('aria-label', 'Créer le toit par ses cotes');
  const champs = [
    ['Longueur (m)', 'longueur'],
    ['Largeur (m)', 'largeur'],
    ['Orientation (°)', 'orientation'],
  ] as const;
  const saisies: Record<string, HTMLInputElement> = {};
  for (const [etiquette, nom] of champs) {
    const i = document.createElement('input');
    i.type = 'text';
    i.inputMode = 'decimal';
    i.setAttribute('step', 'any');
    i.name = nom;
    i.placeholder = etiquette;
    i.setAttribute('aria-label', etiquette);
    i.className = 'rp9-input w-28';
    saisies[nom] = i;
    rangee.appendChild(i);
  }
  const b = document.createElement('button');
  b.type = 'submit';
  b.textContent = 'Créer le toit';
  b.className = 'rp9-btn';
  rangee.appendChild(b);
  rangee.addEventListener('submit', (e) => {
    e.preventDefault();
    creerDepuisSaisie(saisies.longueur.value, saisies.largeur.value, saisies.orientation.value);
  });
  ancre.insertAdjacentElement('afterend', rangee);
  return { rafraichir: () => (rangee.hidden = !deps.vide()), creerDepuisSaisie };
}
