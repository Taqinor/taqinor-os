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

/** ACAL1612 — la ligne « Dans la durée » de l'atelier ERP : la fiche du module servie ne porte pas sa dégradation. */
export const SANS_DEGRADATION = 'Dans la durée : non estimée — la fiche du module ne porte pas sa dégradation.';

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
export function texteSurDevis(placed: number, besoin: number, erp: boolean, devisLie: boolean, duDevis: number | null | undefined, qui = ''): string {
  if (!erp) return `${fmt(placed)} posés / ${fmt(besoin)} au devis`;
  const base = `${fmt(placed)} posés / ${fmt(besoin)} cible`;
  return devisLie && typeof duDevis === 'number' && duDevis > 0 ? `${base} · ${fmt(duDevis)} au devis${qui}` : base;
}

/** ACAL1951 — QUEL devis et QUELLE option : « DEV-202611-0022 (option avec batterie) », précédé d'une espace, lu du payload
 *  de boot (`referenceDevis` = devis lié, `optionCible` = `cible.option` servie). Rien d'inventé : chaque morceau manquant
 *  (cible estimée sans option, devis sans référence) est omis. */
export function quiDuDevis(opts: { hydrate?: { devis?: object | null } | null } | null | undefined): string {
  const p = opts?.hydrate?.devis as Record<string, unknown> | null | undefined;
  const reference = typeof p?.referenceDevis === 'string' ? p.referenceDevis.trim() : '';
  const option = p?.optionCible === 'avec' ? 'avec batterie' : p?.optionCible === 'sans' ? 'sans batterie' : '';
  return `${reference ? ` ${reference}` : ''}${option ? ` (option ${option})` : ''}`;
}

/** ACAL1951 — la suite « · 7 au devis DEV-… (option avec batterie) » d'une note de pose : seulement dans l'atelier ERP, pour un
 *  devis LIÉ et VENDU au compte positif (mêmes conditions que `texteSurDevis`) ; chaîne vide sinon. */
export function suiteAuDevis(ctx: { opts?: { chiffrage?: unknown; devisLie?: boolean; hydrate?: { devis?: object | null } | null }; cibleVendue?: boolean; panneauxDevis?: number | null }): string {
  const n = ctx.panneauxDevis;
  return ctx.opts?.chiffrage !== undefined && ctx.opts.devisLie && ctx.cibleVendue && typeof n === 'number' && n > 0 ? ` · ${fmt(n)} au devis${quiDuDevis(ctx.opts)}` : '';
}

/** R2-13 — le compte de panneaux du devis relu avec le contexte : un nombre strictement positif, sinon `null` (aucun compte). */
export const compteDevis = (v: unknown): number | null => (typeof v === 'number' && v > 0 ? v : null);

/** R2-16 — le texte de la bande « Année 1 → Année N » d'une carte. ERP : UNE économie (la servie, sinon l'estimation prudente) ;
 *  l'année N ne recopie jamais un montant calculé sur une autre base que le servi. Site public : fourchette d'avant. */
export function peindreBande(band: HTMLElement | null, d: CardData, cible: number, erp: boolean, chiffrage: ChiffrageAtelier | null | undefined, factureInconnue: boolean, kwc: number | null = d.kwc): void {
  if (band) band.textContent = texteBandeCarte(d, cible, erp, chiffrage, factureInconnue, kwc);
}

function texteBandeCarte(d: CardData, cible: number, erp: boolean, chiffrage: ChiffrageAtelier | null | undefined, factureInconnue: boolean, kwc: number | null): string {
  if (!(d.annualKwh > 0)) return '';
  const servie = erp ? serviNb(chiffrage?.economie_annee1_mad) : null;
  const prod = (erp ? productionServie(chiffrage, kwc) : null) ?? d.annualKwh; // ACAL1418 — l'Année 1 lit la production de la carte
  // ACAL1612 — l'ERP n'invente aucun taux : la fiche servie ne porte pas sa dégradation, l'année N se tait en disant pourquoi.
  if (erp) return `Année 1 ~${fmt(Math.round(prod))} kWh/an${factureInconnue ? '' : ` (${fmtMad(servie ?? d.savingsLow)}/an)`}. ${SANS_DEGRADATION}`;
  const fac25 = degradationFactor(LIFETIME_YEARS);
  const sav25 = cible > 0 ? annualSavingsMad(prod * fac25, cible) : { low: d.savingsLow * fac25, high: d.savingsHigh * fac25 };
  return texteBande({
    degPct: Math.round(ANNUAL_DEGRADATION * 1000) / 10, annualKwh: prod, kwhFin: prod * fac25, annees: LIFETIME_YEARS, factureInconnue,
    an1: d.savingsHigh, an25: sav25.high,
  });
}

/** R2-17 — la production SERVIE (celle du PDF), seulement à kWc égal : sinon `null` (l'estimation du navigateur reste). */
export function productionServie(chiffrage: ChiffrageAtelier | null | undefined, kwc: number | null): number | null {
  const prod = serviNb(chiffrage?.production_annuelle_kwh);
  const kwcServi = serviNb(chiffrage?.kwc);
  return prod != null && kwcServi != null && kwc != null && Math.abs(kwcServi - kwc) < 0.005 ? prod : null;
}

/** ACAL1418 — le Total « Production estimée » : la production SERVIE à kWc égal (comme la carte), sinon l'estimation du
 *  navigateur, DITE « estimation » dans l'ERP. Site public (`erp` faux) : le texte d'avant. */
export function texteTotalProduction(annualKwh: number, kwc: number | null, erp: boolean, chiffrage: ChiffrageAtelier | null | undefined): string {
  const servie = erp ? productionServie(chiffrage, kwc) : null;
  const sim = erp ? texteSimulation(servie ?? annualKwh, chiffrage) : '';
  if (servie != null) return `${fmt(Math.round(servie))} kWh/an${sim}`;
  return annualKwh > 0 ? `${fmt(Math.round(annualKwh))} kWh/an${erp ? ` · estimation de l’atelier${sim}` : ''}` : '—';
}

/** ACAL1612 — le P50 de la simulation À JOUR (`chiffrage.simulation`, fourni par la page hôte) et l'écart de l'estimation. */
function texteSimulation(kwh: number, chiffrage: ChiffrageAtelier | null | undefined): string {
  const sim = (chiffrage as { simulation?: { p50_kwh?: number | null; a_jour?: boolean } | null } | null | undefined)?.simulation;
  const p50 = sim?.a_jour === true && typeof sim.p50_kwh === 'number' && sim.p50_kwh > 0 ? sim.p50_kwh : null;
  if (p50 == null || !(kwh > 0)) return '';
  const ecart = Math.round(((kwh - p50) / p50) * 100);
  return ` · simulation : ${fmt(Math.round(p50))} kWh/an (écart ${ecart < 0 ? '−' : '+'} ${fmt(Math.abs(ecart))} %)`;
}
