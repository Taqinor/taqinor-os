// R2-16/17 — textes de l'atelier ERP qui lisent le bloc `chiffrage` SERVI. Fonctions pures (aucun DOM, aucun calcul d'argent :
// on affiche ce que le serveur a servi, ou l'estimation prudente déjà calculée par l'appelant). Site public : jamais appelées.
import { fmt, fmtMad } from './dom';

/** Une grandeur SERVIE (`etat: 'servi'` + nombre), sinon `null`. */
export const serviNb = (g: { valeur: number | null; etat: string } | null | undefined): number | null =>
  g?.etat === 'servi' && typeof g.valeur === 'number' ? g.valeur : null;

/** La phrase « Pose très au-dessus de la consommation » : au-delà de DEUX fois la consommation, avec les deux nombres. */
export function phraseSurplus(annualKwh: number, consommationKwh: number | null | undefined): string {
  if (!((consommationKwh ?? 0) > 0) || !(annualKwh > 2 * (consommationKwh as number))) return '';
  return ` Pose très au-dessus de la consommation : ${fmt(Math.round(annualKwh))} kWh/an produits pour ${fmt(Math.round(consommationKwh as number))} kWh/an consommés.`;
}

/** La bande « Année 1 → Année N ». `an25` nul = l'année N est dite sans montant (jamais un montant inventé). */
export function texteBande(p: { degPct: number; annualKwh: number; kwhFin: number; annees: number; factureInconnue: boolean; an1: number; an25: number | null }): string {
  const { factureInconnue: fi } = p;
  return (
    `Dans la durée (dégradation ~${p.degPct.toLocaleString('fr-FR')} %/an) : ` +
    `Année 1 ~${fmt(Math.round(p.annualKwh))} kWh/an${fi ? '' : ` (${fmtMad(p.an1)}/an)`} → ` +
    `Année ${p.annees} ~${fmt(Math.round(p.kwhFin))} kWh/an${fi ? '.' : p.an25 == null ? '.' : ` (${fmtMad(p.an25)}/an). Économies toujours plafonnées à votre facture.`}`
  );
}
