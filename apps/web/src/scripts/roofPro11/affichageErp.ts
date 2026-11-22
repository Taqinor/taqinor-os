// R2-16/17 — textes de l'atelier ERP qui lisent le bloc `chiffrage` SERVI. Fonctions pures (aucun DOM, aucun calcul d'argent :
// on affiche ce que le serveur a servi, ou l'estimation prudente déjà calculée par l'appelant). Site public : jamais appelées.
import { fmt, fmtMad } from './dom';
import { annualSavingsMad, degradationFactor, ANNUAL_DEGRADATION, LIFETIME_YEARS } from '../../lib/estimatorBrainV2';
import { type CardData, type ChiffrageAtelier } from './types';

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

/** R2-13/22/23 — « N posés / M cible » (atelier ERP) et, pour un devis LIÉ au compte connu, « · K au devis ». Site public : « au devis ». */
export function texteSurDevis(placed: number, besoin: number, erp: boolean, devisLie: boolean, duDevis: number | null | undefined): string {
  if (!erp) return `${fmt(placed)} posés / ${fmt(besoin)} au devis`;
  const base = `${fmt(placed)} posés / ${fmt(besoin)} cible`;
  return devisLie && typeof duDevis === 'number' && duDevis > 0 ? `${base} · ${fmt(duDevis)} au devis` : base;
}

/** R2-13 — le compte de panneaux du devis relu avec le contexte : un nombre strictement positif, sinon `null` (aucun compte). */
export const compteDevis = (v: unknown): number | null => (typeof v === 'number' && v > 0 ? v : null);

/** R2-16 — le texte de la bande « Année 1 → Année N » d'une carte. ERP : UNE économie (la servie, sinon l'estimation prudente) ;
 *  l'année N ne recopie jamais un montant calculé sur une autre base que le servi. Site public : fourchette d'avant. */
export function peindreBande(band: HTMLElement | null, d: CardData, cible: number, erp: boolean, chiffrage: ChiffrageAtelier | null | undefined, factureInconnue: boolean): void {
  if (band) band.textContent = texteBandeCarte(d, cible, erp, chiffrage, factureInconnue);
}

function texteBandeCarte(d: CardData, cible: number, erp: boolean, chiffrage: ChiffrageAtelier | null | undefined, factureInconnue: boolean): string {
  if (!(d.annualKwh > 0)) return '';
  const servie = erp ? serviNb(chiffrage?.economie_annee1_mad) : null;
  const fac25 = degradationFactor(LIFETIME_YEARS);
  const sav25 = cible > 0 ? annualSavingsMad(d.annualKwh * fac25, cible) : { low: d.savingsLow * fac25, high: d.savingsHigh * fac25 };
  return texteBande({
    degPct: Math.round(ANNUAL_DEGRADATION * 1000) / 10, annualKwh: d.annualKwh, kwhFin: d.annualKwh * fac25, annees: LIFETIME_YEARS, factureInconnue,
    an1: erp ? (servie ?? d.savingsLow) : d.savingsHigh, an25: erp ? (servie != null ? null : sav25.low) : sav25.high,
  });
}

/** R2-17 — la production SERVIE (celle du PDF), seulement à kWc égal : sinon `null` (l'estimation du navigateur reste). */
export function productionServie(chiffrage: ChiffrageAtelier | null | undefined, kwc: number | null): number | null {
  const prod = serviNb(chiffrage?.production_annuelle_kwh);
  const kwcServi = serviNb(chiffrage?.kwc);
  return prod != null && kwcServi != null && kwc != null && Math.abs(kwcServi - kwc) < 0.005 ? prod : null;
}
