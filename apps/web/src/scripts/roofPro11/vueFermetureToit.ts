/**
 * ACAL1422 — la caméra après « Terminer le tracé » / « Créer le toit ».
 *
 * Site public : inchangé (cadrage plafonné à 19, vue inclinée `PITCH_VIEW`). Atelier ERP : la vue COURANTE est gardée
 * (Plan reste Plan) et le toit est cadré avec le plafond de zoom de l'atelier (`cadrageAnneaux`, même formule que
 * `cadrerToit`), au lieu de reculer à ~8 % de la carte. PUR : aucune carte, rien d'écrit au document.
 */
import { cadrageAnneaux, zoomToFitRing, type LngLat } from '../../lib/roof';
import { PITCH_VIEW } from './constants';

/** Le plafond de zoom de l'atelier ERP (le même que `useAtelierBoot.js::ZOOM_MAX_CADRAGE_ATELIER`). */
export const ZOOM_MAX_FERMETURE_ATELIER = 22;

export interface EntreeFermeture {
  anneau: readonly LngLat[];
  centre: LngLat;
  zoomCourant: number;
  pitchCourant: number;
  largeurPx: number;
  hauteurPx: number;
  /** Atelier ERP (vrai) ou site public (faux). */
  erp: boolean;
}

export function cibleFermetureToit(e: EntreeFermeture): { center: LngLat; zoom: number; pitch: number } {
  if (e.erp) {
    const cadre = cadrageAnneaux([[...e.anneau]], e.largeurPx, e.hauteurPx, { zoomMax: ZOOM_MAX_FERMETURE_ATELIER });
    if (cadre) return { ...cadre, pitch: e.pitchCourant };
  }
  return { center: e.centre, zoom: e.anneau.length >= 3 ? zoomToFitRing([...e.anneau]) : e.zoomCourant, pitch: PITCH_VIEW };
}
