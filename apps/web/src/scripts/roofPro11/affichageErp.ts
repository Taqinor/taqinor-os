// R2-16/17 — textes de l'atelier ERP qui lisent le bloc `chiffrage` SERVI. Fonctions pures (aucun DOM, aucun calcul d'argent :
// on affiche ce que le serveur a servi, ou l'estimation prudente déjà calculée par l'appelant). Site public : jamais appelées.
import { fmt, fmtMad } from './dom';
import { annualSavingsMad, degradationFactor, ANNUAL_DEGRADATION, LIFETIME_YEARS } from '../../lib/estimatorBrainV2';
import { type CardData, type ChiffrageAtelier } from './types';
import { memeTaille, phraseTailles, tailleDifferente } from './tailleConception'; // T4-X9 — LE prédicat de taille
import { catalogueAvecModulesDuDocument, estRefus, lireModulesDisponibles, resoudreModuleDuPan } from './moduleSelect'; // T4-X8-012 (une cible)

/** ACAL2022 — ce que l'atelier ERP dit à la place d'un chiffre qu'il ne calcule plus : la production et l'économie sont celles de
 *  la conception SERVIE ; pendant le dessin (kWc posé ≠ kWc servi) il ne montre que panneaux et kWc posés. */
export const AU_PROCHAIN_ENREGISTREMENT = 'production au prochain enregistrement';
export const ECONOMIE_AU_PROCHAIN_ENREGISTREMENT = 'économie au prochain enregistrement';
/** M5 — la vraie raison d'une valeur absente. Au niveau de règles 14, enregistrer la pose ne change PAS la taille de la
 *  conception : si la taille servie diffère de celle posée, la valeur ne viendra jamais — on le dit avec les deux tailles.
 *  « au prochain enregistrement » ne reste que là où il est vrai (même taille mais bloc pas encore relu ; rien d'enregistré). */
export function raisonSansValeur(chiffrage: ChiffrageAtelier | null | undefined, kwc: number | null | undefined, grandeur: 'production' | 'économie'): string {
  // T4-X9-007 — tailles différentes : la case d'un chiffre clé dit « — » ; la phrase se lit UNE fois, en texte courant,
  // sous les cartes qu'elle explique (`phraseTaillesDuChiffrage`).
  if (tailleDifferente(serviNb(chiffrage?.kwc), kwc)) return '—';
  // T4-X2-006 / T4-X9-013 — bloc « non servi » (calepinage sans lead, agricole) : aucune conception ne viendra à
  // l'enregistrement ; la case dit « — » (la production est celle de la simulation, relayée à part).
  if (chiffrage?.production_annuelle_kwh?.etat === 'non_servi') return '—';
  return grandeur === 'production' ? AU_PROCHAIN_ENREGISTREMENT : ECONOMIE_AU_PROCHAIN_ENREGISTREMENT;
}

/** T4-X9-007 — la phrase des deux tailles, en texte courant (« Production et économie calculées pour la conception du
 *  lead : 4,40 kWc — votre pose en compte 5,68 kWc. »), ou `''` quand les tailles sont égales ou inconnues. */
export function phraseTaillesDuChiffrage(chiffrage: ChiffrageAtelier | null | undefined, kwc: number | null | undefined): string {
  if (estPompage(chiffrage)) return ''; // ACAL1268 — ni production ni économie dans l'atelier d'un lead de pompage
  const servi = serviNb(chiffrage?.kwc);
  return tailleDifferente(servi, kwc) ? phraseTailles('Production et économie', servi as number, kwc as number, true) : '';
}
/** ACAL1268 (D-ACAL-66 = outil_pose) — le bloc `chiffrage` passé à l'outil porte le marché du lead (`marche`, servi par le
 *  design-context) : un atelier de POMPAGE ne dit ni kWh de réseau ni économies — la pose (panneaux, kWc) reste. */
export const estPompage = (chiffrage: ChiffrageAtelier | null | undefined): boolean =>
  (chiffrage as { marche?: string } | null | undefined)?.marche === 'agricole';

/** ACAL2022 — le bloc servi n'a pas pu être relu (hors ligne) : les valeurs gardées sont celles du dernier calcul. */
export const VALEURS_HORS_LIGNE = 'valeurs du dernier calcul, hors ligne';

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

/** T4-X8-012 (une cible) — LA cible de l'atelier ERP : celle que le serveur sert pour CE calepinage (`design-context` → `cible`,
 *  projetée par l'ERP en `hydrate.devis.cible` + `origineCible` + `libelleOrigineCible`), comptée dans le module POSÉ (la table
 *  servie `panneaux_selon_watt`, comme la carte « Couvrir la facture » ; repli : le compte de la conception si le module posé a sa
 *  puissance). `origine` = les MOTS de la carte « Cible — panneaux » (« Source de la cible » : Factures du lead, Devis lié…).
 *  `null` : aucune cible servie, ou aucun compte servi pour ce module, ou site public — les phrases gardent alors leur texte
 *  d'avant ; le nombre choisi s'appelle « Panneaux à poser » (D-ACAL-155), jamais « cible » quand une cible est servie. */
export interface CibleAtelier { panneaux: number; origine: string }
export function cibleDeLAtelier(ctx: { opts?: { chiffrage?: unknown; hydrate?: { devis?: object | null } | null } | null }, watt: number | null | undefined): CibleAtelier | null {
  if (ctx.opts?.chiffrage === undefined) return null;
  const p = ctx.opts?.hydrate?.devis as { origineCible?: unknown; libelleOrigineCible?: unknown; cible?: { panneaux?: unknown; panel_watt?: unknown } | null } | null | undefined;
  const origine = typeof p?.libelleOrigineCible === 'string' ? p.libelleOrigineCible.trim() : '';
  if (!origine || typeof p?.origineCible !== 'string') return null;
  const conception = Number(p.cible?.panneaux);
  const wattConception = Number(p.cible?.panel_watt);
  const memeModule = !(wattConception > 0) || !(Number(watt) > 0) || Math.abs(Number(watt) - wattConception) < 0.5;
  const panneaux = besoinDeLaFacture(ctx.opts, watt) ?? (conception > 0 && memeModule ? conception : null);
  return panneaux ? { panneaux, origine } : null;
}

/** La puissance (Wc) du module posé sur le pan actif — le même résolveur que la pastille du panneau de pose (`layoutEditor`) ;
 *  `null` quand le module désigné est refusé. Sert à compter LA cible dans ce module. */
export function wattDuPanActif(ctx: { opts?: { modulesDisponibles?: unknown } | null; modulesDuDocument?: Array<Record<string, unknown>>; activeArea?: () => { moduleId?: string | null } | undefined }): number | null {
  const m = resoudreModuleDuPan(catalogueAvecModulesDuDocument(lireModulesDisponibles(ctx.opts?.modulesDisponibles).choisissables, ctx.modulesDuDocument).catalogue, ctx.activeArea?.()?.moduleId);
  return estRefus(m) ? null : m.pmaxWc;
}

/** Le nombre contre lequel « Posés ÷ cible » se calcule : LA cible servie (module posé `watt`), sinon le nombre à poser comme avant. */
export const cibleOuABesoin = (ctx: Parameters<typeof cibleDeLAtelier>[0] & { neededPanels: number }, watt: number | null | undefined): number =>
  cibleDeLAtelier(ctx, watt)?.panneaux ?? ctx.neededPanels;

/** L'écart entre ce qui est posé et LA cible, avec les deux nombres déjà à l'écran (jamais un troisième). */
const ecartALaCible = (placed: number, cible: number): string =>
  placed === cible ? '' : ` · ${fmt(Math.abs(placed - cible))} de ${placed > cible ? 'plus' : 'moins'} que la cible`;

/** « seuls N tiennent » dit un manque : faux quand ce que le toit tient atteint LA cible servie — la phrase dit alors seulement
 *  que le toit n'en tient pas davantage (le nombre à poser demandé en voulait plus). Sans cible servie : la phrase d'avant. */
export const phraseTiennent = (placed: number, cible: CibleAtelier | null): string =>
  cible && placed >= cible.panneaux ? 'le toit n’en tient pas davantage' : `seuls ${fmt(placed)} tiennent`;

/** R2-13/22/23 — « N posés / M cible » (atelier ERP) et, pour un devis LIÉ au compte connu, « · K au devis ». Site public : « au devis ».
 *  T4-X8-012 (une cible) — avec une cible SERVIE (`cible`), M est LA cible suivie de sa source (mots de la carte) et de l'écart :
 *  « 16 posés / 7 cible (Factures du lead) · 9 de plus que la cible ». Sans cible servie : M = le nombre à poser, comme avant. */
export function texteSurDevis(placed: number, besoin: number, erp: boolean, devisLie: boolean, duDevis: number | null | undefined, qui = '', cible: CibleAtelier | null = null): string {
  if (!erp) return `${fmt(placed)} posés / ${fmt(besoin)} au devis`;
  // ACAL1665 — « le plus de panneaux » (le plafond 400) n'est pas une cible : dit en mots, jamais « / 400 cible ».
  const base = cible ? `${fmt(placed)} posés / ${fmt(cible.panneaux)} cible (${cible.origine})${ecartALaCible(placed, cible.panneaux)}` : estLePlus(besoin) ? `${fmt(placed)} posés — le plus possible` : `${fmt(placed)} posés / ${fmt(besoin)} cible`;
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
  if (erp && estPompage(chiffrage)) return ''; // ACAL1268 — la bande « Année 1 ~… kWh/an » n'a pas lieu d'être
  if (erp) {
    // ACAL2022 — l'ERP ne montre que le SERVI à kWc égal, jamais l'estimation du navigateur ; pendant le dessin : « au prochain enregistrement ».
    const servieProd = productionServie(chiffrage, kwc); // ACAL1418 — l'Année 1 lit la production de la carte
    // T4-X2-006 (rejeu R5B) — une simulation À JOUR existe : l'Année 1 la lit (même chiffre que le Total), au lieu de dire
    // « au prochain enregistrement » alors que la conception est enregistrée et simulée. Sinon la raison vraie.
    if (servieProd == null) {
      const p50 = p50ADate(chiffrage);
      if (p50 != null) return `Année 1 ~${fmt(Math.round(p50))} kWh/an (simulation). ${SANS_DEGRADATION}`;
      return `Année 1 : ${raisonSansValeur(chiffrage, kwc, 'production')}. ${SANS_DEGRADATION}`;
    }
    const servie = serviNb(chiffrage?.economie_annee1_mad);
    // ACAL1612 — l'ERP n'invente aucun taux : la fiche servie ne porte pas sa dégradation, l'année N se tait en disant pourquoi.
    return `Année 1 ~${fmt(Math.round(servieProd))} kWh/an${factureInconnue || servie == null ? '' : ` (${fmtMad(servie)}/an)`}. ${SANS_DEGRADATION}`;
  }
  const prod = d.annualKwh;
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
  return prod != null && memeTaille(serviNb(chiffrage?.kwc), kwc) ? prod : null;
}

/** ACAL1418 — le Total « Production estimée » : la production SERVIE à kWc égal (comme la carte), sinon l'estimation du
 *  navigateur, DITE « estimation » dans l'ERP. Site public (`erp` faux) : le texte d'avant. */
export function texteTotalProduction(annualKwh: number, kwc: number | null, erp: boolean, chiffrage: ChiffrageAtelier | null | undefined): string {
  if (!erp) return annualKwh > 0 ? `${fmt(Math.round(annualKwh))} kWh/an` : '—';
  if (estPompage(chiffrage)) return '—'; // ACAL1268
  const servie = productionServie(chiffrage, kwc);
  if (servie != null) return `${fmt(Math.round(servie))} kWh/an${texteSimulation(servie, chiffrage)}`;
  // ACAL2022 (T4-X2-006) — une simulation à jour existe : l'estimation de l'atelier n'est plus montrée à côté d'elle.
  const p50 = p50ADate(chiffrage);
  if (p50 != null) return `${fmt(Math.round(p50))} kWh/an · simulation`;
  return annualKwh > 0 ? raisonSansValeur(chiffrage, kwc, 'production') : '—';
}

/** Le P50 de la simulation À JOUR (`chiffrage.simulation`, fourni par la page hôte), sinon `null`. */
function p50ADate(chiffrage: ChiffrageAtelier | null | undefined): number | null {
  const sim = (chiffrage as { simulation?: { p50_kwh?: number | null; a_jour?: boolean } | null } | null | undefined)?.simulation;
  return sim?.a_jour === true && typeof sim.p50_kwh === 'number' && sim.p50_kwh > 0 ? sim.p50_kwh : null;
}

/** ACAL2022 / ACAL2023 — la part « production ÷ consommation » SERVIE (`chiffrage.couverture_pct`, % de la conception), à kWc égal. */
export function couvertureServie(chiffrage: ChiffrageAtelier | null | undefined, kwc: number | null): number | null {
  const pct = serviNb(chiffrage?.couverture_pct);
  return pct != null && memeTaille(serviNb(chiffrage?.kwc), kwc) ? pct : null;
}

/** ACAL2022 / T4-X9-003 — l'économie SERVIE, seulement au kWc de la conception — la carte ET le Total (avant, sans `kwc`,
 *  le Total la montrait sans contrôle, à côté d'une pose d'une autre taille). */
export function economieServie(chiffrage: ChiffrageAtelier | null | undefined, kwc?: number | null): number | null {
  const eco = serviNb(chiffrage?.economie_annee1_mad);
  return eco != null && memeTaille(serviNb(chiffrage?.kwc), kwc) ? eco : null;
}

/** ACAL2022 — le texte de l'économie de la carte et du Total : site public (`chiffrage` absent) ⇒ l'estimation du
 *  navigateur ; ERP ⇒ la servie (au kWc posé), sinon « au prochain enregistrement » — jamais l'estimation. */
export function texteEconomie(chiffrage: ChiffrageAtelier | null | undefined, kwc: number | null | undefined, estime: string): string {
  if (chiffrage === undefined) return estime;
  const servie = economieServie(chiffrage, kwc);
  return servie != null ? `${fmtMad(servie)}/an` : estime.startsWith('—') ? estime : raisonSansValeur(chiffrage, kwc, 'économie');
}

/** ACAL1612 — le P50 de la simulation À JOUR et l'écart de la production servie. */
function texteSimulation(kwh: number, chiffrage: ChiffrageAtelier | null | undefined): string {
  const p50 = p50ADate(chiffrage);
  if (p50 == null || !(kwh > 0)) return '';
  const ecart = Math.round(((kwh - p50) / p50) * 100);
  return ` · simulation : ${fmt(Math.round(p50))} kWh/an (écart ${ecart < 0 ? '−' : '+'} ${fmt(Math.abs(ecart))} %)`;
}

// ═══════════ T4-X8-012 — « LE PLUS DE PANNEAUX » N'EST PAS UN BESOIN DE FACTURE ═══════════
// « Le plus de panneaux » (atelier ERP) pose le PLAFOND du besoin (`optimizer.ts::clampNeeded`, 400) : « tout ce qui tient ».
// Enregistré dans le pan (`neededPanels`), il était relu comme le nombre de panneaux que la FACTURE demande (« PANNEAUX
// NÉCESSAIRES 400 », « 9 posés / 400 cible »). Le champ dit le besoin de la facture, la note dit le choix en mots.

/** Le plafond du besoin (`clampNeeded`) : un besoin qui l'atteint veut dire « le plus de panneaux », jamais « 400 nécessaires ». */
export const LE_PLUS_DE_PANNEAUX = 400;
export const estLePlus = (besoin: number | null | undefined): boolean => typeof besoin === 'number' && besoin >= LE_PLUS_DE_PANNEAUX;
/** L'atelier ERP (`opts.chiffrage` défini) dont le pan actif porte « le plus de panneaux » : aucune couverture ni « besoin (400) »
 *  ne se calcule contre ce plafond. Site public : jamais (texte d'avant). */
export const lePlusErp = (ctx: { opts?: { chiffrage?: unknown } | null; neededPanels: number }): boolean =>
  ctx.opts?.chiffrage !== undefined && estLePlus(ctx.neededPanels);

/** Le besoin de la FACTURE compté dans le module posé (`watt`) : le compte SERVI par `modules-disponibles/`
 *  (`panneaux_selon_watt`, LA règle du moteur `panneaux_pour_la_meme_puissance` — le même chiffre que la carte « Couvrir la
 *  facture »), porté par le payload de boot (`hydrate.devis.panneauxSelonWatt`). `null` quand il n'est pas servi. */
export function besoinDeLaFacture(opts: { hydrate?: { devis?: object | null } | null } | null | undefined, watt: number | null | undefined): number | null {
  const table = (opts?.hydrate?.devis as { panneauxSelonWatt?: Record<string, unknown> } | null | undefined)?.panneauxSelonWatt;
  const n = table && typeof watt === 'number' && watt > 0 ? table[String(watt)] : null;
  return typeof n === 'number' && Number.isInteger(n) && n > 0 ? n : null;
}

/** Le champ « Panneaux à poser » (site public : « Panneaux nécessaires », inchangé) : en ERP sur « le plus de panneaux », le besoin de la facture (« — » s'il n'est pas
 *  servi) et `data-le-plus="1"` (lu par l'étape Panneaux du Guidé, qui garde « Le plus de panneaux » choisi) ; sinon le
 *  besoin tel quel. `data-besoin-facture` garde le chiffre affiché pour le re-poser à la sortie du champ. */
export function peindreChampBesoin(el: HTMLInputElement, besoin: number, erp: boolean, facture: number | null, ecrire: boolean): void {
  const lePlus = erp && estLePlus(besoin);
  el.dataset.lePlus = lePlus ? '1' : '';
  el.dataset.besoinFacture = lePlus && facture ? fmt(facture) : '';
  if (ecrire) el.value = lePlus ? (facture ? fmt(facture) : '—') : besoin > 0 ? fmt(besoin) : '—';
}

/** La note du nombre de panneaux sur « le plus de panneaux » : le choix dit en mots, puis le besoin de la facture s'il est servi. */
export function noteLePlus(poses: number, facture: number | null): string {
  return `Vous avez choisi le plus de panneaux possible : ${fmt(poses)} posés.${facture ? ` Le besoin de la facture : ${fmt(facture)}.` : ''}`;
}
