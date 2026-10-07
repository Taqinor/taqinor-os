// SPL195 — Modèle tarifaire de l'écran devis : barèmes ONEE/Lydec/Redal,
// factures ⇄ kWh, contrôles de saisie, modèle « deux factures ».
// DÉPLACEMENT PUR depuis features/ventes/solar.js (aucune logique changée) ;
// module feuille : n'importe rien.

// ── QF4/QF5 — Modèle « deux factures » par tranche (MIROIR JS) ───────────────
// Port fidèle de backend apps/ventes/quote_engine/pricing.py : mêmes tables de
// tranches, mêmes formules. Permet à l'écran d'afficher EXACTEMENT le même
// calcul que le PDF (facture sans vs avec solaire, économie réelle) au lieu
// d'une approximation production × autoconsommation × prix moyen.
//
// QF5 — divergence de tarif corrigée : `KWH_PRICE` (1.75) reste le défaut
// historique de `computeROI` (aligné sur CompanyProfile.onee_tarif_kwh, le
// repli RÉEL en pratique) ; `FALLBACK_KWH_PRICE` (1.20) mirror l'ultime repli
// `_FALLBACK_KWH_PRICE` de pricing.py, utilisé UNIQUEMENT quand ni tranche ni
// tarif société ne sont disponibles (repli en cascade, comme le backend).
export const FALLBACK_KWH_PRICE = 1.20 // MAD/kWh — miroir pricing.py._FALLBACK_KWH_PRICE

// Tables de tranches (miroir pricing.py — mêmes valeurs, mêmes plafonds).
// Format : [plafond_kWh_mensuel | null, prix_MAD_kWh_TTC].
//
// ═══ ORDRE FONDATEUR (18/08) — LE BARÈME RÉSIDENTIEL EST SÉLECTIF ═══════════
// « The client will go down in the price per kWh because he will be below 500
//   kWh per month — I want the new price per kWh to be used so the savings are
//   real. »
// Le barème BT marocain n'est pas purement progressif : progressif jusqu'au
// seuil (150 kWh/mois), puis SÉLECTIF — franchir une marche re-tarife TOUTE la
// consommation du mois au prix de SA tranche. 700 kWh/mois se paient donc
// 1,5958 MAD/kWh sur les 700 ; le résiduel de 280 kWh après solaire retombe à
// 1,1676 MAD/kWh sur la totalité. C'est la baisse de prix décrite par le
// fondateur, et elle vaut bien plus que les seuls kWh effacés.
//
// `trancheTable` attache la règle sélective à la table SANS changer sa forme :
// la table reste un tableau de paires (itération, deepEqual, JSON inchangés).
function trancheTable(pairs, selectif) {
  if (selectif) Object.defineProperty(pairs, 'selectif', { value: selectif, enumerable: false })
  return pairs
}

// ONEE — barème « BASSE TENSION / usage domestique », prix consommateur TTC.
// MÊME grille que l'estimateur public (apps/web/src/lib/estimatorBrainV2.ts
// REGIE_TARIFF) et que pricing.py ONEE_TRANCHES : site et ERP annoncent la
// même économie.
//
// SOURCE VÉRIFIÉE (consultée le 18/08/2026) — grille officielle d'une régie de
// distribution régulée appliquant le barème national : RADEEJ (El Jadida),
// « Basse Tension : Tarif en DH/kWh TTC »,
// https://radeej.ma/assets/espace%20client/elec%20tarif.pdf. Corroboration
// indépendante (page mise à jour le 18/08/2026) : https://kherba.com/tarifs.
//   · ≤ 150 kWh/mois → « Tarif Progressif » : 0-100 = 0,9010 ; 101-150 = 1,0732.
//   · > 150 kWh/mois → « Tarif Sélectif » : 151-200 = 1,0732 ; 201-300 = 1,1676 ;
//     301-500 = 1,3817 ; > 500 = 1,5958 — la tolérance officielle de 10 kWh/mois
//     par tranche donne les bornes effectives 210/310/510.
// BASE LÉGALE DU MÉCANISME : arrêtés ministériels n° 2451.14 / 2682.14, BO
// n° 6275 bis du 22/07/2014 (appliqués au 01/08/2014) — « facturer la totalité
// de la consommation mensuelle au tarif de la tranche dans laquelle elle se
// situe ». Le tarif de vente BT n'est pas publié par l'ANRE (elle ne régule que
// l'usage du réseau) ; refonte annoncée ~mars 2027, à re-vérifier alors.
// HAUT DE GRILLE — POINT OUVERT (fondateur 18/08) : sa correction de fond est
// confirmée (1,4017 était trop bas), mais le taux publié en USAGE DOMESTIQUE
// > 500 kWh/mois est 1,5958 ; les taux ~1,69-1,71 de la même grille sont
// d'autres usages (force motrice > 500 = 1,6758 ; éclairage patenté > 150 =
// 1,7090). On encode le taux domestique VÉRIFIÉ, jamais un chiffre inventé.
// Remplace l'ancienne grille QX38 (100/250/400/∞ à 0,9010/1,0258/1,2515/1,4017),
// purement progressive et marquée « à confirmer » : elle contredisait la grille
// officielle sur les seuils ET sur les prix.
//
// ORDRE FONDATEUR (19/08/2026) — TVA 20 % depuis le 01/01/2026 (16 % en 2024,
// 18 % en 2025) : les six prix RADEEJ ci-dessus étaient encore au taux 2025
// (18 %). Re-dérivés HT × 1,20 (HT = TTC 2025 ÷ 1,18) ; ancre fondateur
// (facture réelle) = tranche > 500 kWh = 1,622856 MAD/kWh TTC. Détail complet
// de la dérivation HT/TTC par tranche : apps/ventes/quote_engine/pricing.py
// ONEE_TRANCHES (miroir exact). Prochaine hausse de TVA : refaire HT × nouveau
// taux sur les six bases HT documentées là-bas — jamais repartir d'un TTC
// déjà taxé. ÉDITABLE PAR SOCIÉTÉ : Paramètres → Tarification & ROI.
//
// DÉCISION FONDATEUR D5 (29/08/2026) — TRANCHE 5 RECALÉE SUR LA FACTURE. La
// tranche 311-510 vaut 1,381704 et NON l'extrapolation « HT constant » : la
// facture SRM Casablanca-Settat n° 643769639 du 08/05/2026 (359 kWh × 1,15142
// HT = 496,03 TTC) donne 1,15142 × 1,20 = 1,381704, et la facture du
// 20/01/2026 corrobore (T5 2025 = 1,3817 TTC). Au passage TVA 18 → 20 %, c'est
// le TTC qui est resté CONSTANT et le HT qui a baissé — l'inverse de ce que le
// repo supposait. Une FACTURE RÉELLE supplante toujours une extrapolation ; les
// cinq autres tranches, sans facture 2026, gardent leur valeur dérivée.
// La valeur de référence vit côté serveur dans
// apps/ventes/quote_engine/bareme.py (barème étalonné sur trois factures).
export const ONEE_TRANCHES = trancheTable([
  [100, 0.916272],   // progressif   0-100          — HT 0,76356 × TVA 20% (2026)
  [150, 1.091388],   // progressif 101-150          — HT 0,90949 × TVA 20% (2026)
  [200, 1.091388],   // sélectif 151-200 (eff. 210) — idem
  [300, 1.187388],   // sélectif 201-300 (eff. 310) — HT 0,98949 × TVA 20% (2026)
  [500, 1.381704],   // sélectif 301-500 (eff. 510) — PROUVÉ FACTURE (D5) :
                     // 1,15142 HT × TVA 20% ; voir la note ci-dessus
  [null, 1.622856],  // sélectif > 500  (eff. 510+) — HT 1,35238 × TVA 20% (2026, ancre)
], { seuil: 150, tolerance: 10 })
// Q7 (decision fondateur du 20/08/2026) — UN SEUL BAREME NATIONAL. Les grilles
// « approximatives » Lydec et Redal disparaissent : elles etaient inventees
// (trois paliers ronds « a confirmer ») et faisaient diverger l'ecran du
// barame national sur un meme client. Les trois distributeurs lisent la MEME
// grille (editable par societe cote backend) ; le nom du distributeur reste un
// LIBELLE. Miroir EXACT de quote_engine/pricing.py UTILITY_TABLES.
export const UTILITY_TABLES = {
  onee: ONEE_TRANCHES, lydec: ONEE_TRANCHES, redal: ONEE_TRANCHES,
}

function resolveTranches(utility, tranchesOverride) {
  if (tranchesOverride && tranchesOverride.length) return { table: tranchesOverride, approx: false }
  const key = (utility || '').toLowerCase()
  // Q7 — plus aucune table approximative : approx est toujours false.
  if (key && UTILITY_TABLES[key]) return { table: UTILITY_TABLES[key], approx: false }
  // CAD167 (miroir EXACT de pricing._resolve_tranches) — un distributeur NOMMÉ
  // hors table (les douze SRM régionales, « autre », Amendis) lit la grille
  // NATIONALE (Q7) au lieu de retomber sur factures ÷ 1,20 MAD/kWh. Sans
  // distributeur du tout, le repli étiqueté reste (test_cad167 le verrouille).
  if (String(utility ?? '').trim()) return { table: UTILITY_TABLES.onee, approx: false }
  return { table: null, approx: false }
}

// Règle sélective portée par la table (miroir pricing._selective_rule) :
// { seuil, tolerance } ou null pour une table purement progressive.
function selectiveRule(tranches) {
  const r = tranches && tranches.selectif
  if (!r || !(r.seuil > 0)) return null
  return { seuil: r.seuil, tolerance: r.tolerance || 0 }
}

// Sépare une table plate en bandes progressives (≤ seuil) / sélectives (> seuil).
// Miroir pricing._split_tranches.
function splitTranches(tranches, seuil) {
  const prog = []
  const sel = []
  for (const b of tranches) {
    if (b[0] != null && b[0] <= seuil) prog.push(b)
    else sel.push(b)
  }
  return { prog, sel }
}

// Facture PROGRESSIVE (MAD) : chaque kWh au prix de SA tranche.
// Miroir pricing._progressive_bill.
function progressiveBill(kwhMensuel, bandes) {
  let remaining = kwhMensuel
  let prevCeiling = 0
  let totalCost = 0
  for (const [ceiling, price] of bandes) {
    if (ceiling == null) { totalCost += remaining * price; remaining = 0; break }
    const consumed = Math.min(remaining, ceiling - prevCeiling)
    totalCost += consumed * price
    remaining -= consumed
    prevCeiling = ceiling
    if (remaining <= 0) break
  }
  if (remaining > 0 && bandes.length) totalCost += remaining * bandes[bandes.length - 1][1]
  return totalCost
}

// Facture mensuelle TTC (MAD) d'une consommation — SOURCE UNIQUE du prix d'un
// volume mensuel de kWh. Miroir EXACT de pricing._monthly_bill_from_kwh et de
// billMAD (apps/web/src/lib/estimatorBrainV2.ts) :
//  · table PROGRESSIVE (Lydec, Redal, barème vendeur) : chaque kWh au prix de
//    SA tranche — comportement historique inchangé ;
//  · table SÉLECTIVE (ONEE) : progressif jusqu'au seuil, puis TOUTE la conso au
//    tarif de sa tranche (tolérance de bord incluse), plancher à la facture
//    progressive du seuil.
// Monotone non décroissante par construction.
export function monthlyBillFromKwh(kwhMensuel, tranches) {
  if (!(kwhMensuel > 0)) return 0
  const rule = selectiveRule(tranches)
  if (!rule) return progressiveBill(kwhMensuel, tranches)
  const { prog, sel } = splitTranches(tranches, rule.seuil)
  if (kwhMensuel <= rule.seuil) return progressiveBill(kwhMensuel, prog)
  let rate = sel.length ? sel[sel.length - 1][1] : FALLBACK_KWH_PRICE
  for (const [ceiling, price] of sel) {
    if (ceiling == null || kwhMensuel <= ceiling + rule.tolerance) { rate = price; break }
  }
  return Math.max(kwhMensuel * rate, progressiveBill(rule.seuil, prog))
}

// Inverse NUMÉRIQUE de monthlyBillFromKwh pour une table SÉLECTIVE — miroir
// EXACT de pricing._kwh_from_bill_bisect et de billToAnnualKwh (site).
// TROUS : la règle sélective rend la facture DISCONTINUE (à 210 kWh elle saute
// de 210 × 1,0732 = 225,37 MAD à 210 × 1,1676 = 245,20 MAD — aucune conso ne
// produit 235 MAD). La dichotomie converge vers inf{ k : facture(k) ≥ montant },
// donc un montant tombé dans un trou est résolu à la BORNE BASSE du saut
// (210 kWh) : jamais une conso que le barème ne peut produire, et toujours le
// côté prudent (moins de kWh ⇒ système plus petit, économies plus petites).
// ERR-QAH-DIFF-KWH-HORS-PLAGE — HORS PLAGE ⇒ `null`, JAMAIS LA BORNE (miroir
// de la garde QJR158 (e) de `pricing._kwh_from_bill_bisect`) : une facture
// qu'aucune consommation ≤ 1e6 kWh/mois ne produit faisait converger la
// dichotomie vers ce plafond (≈ 1 024 000 kWh « exacts »).
function kwhFromBillBisect(bill, tranches) {
  let lo = 0
  let hi = 1000
  while (monthlyBillFromKwh(hi, tranches) < bill && hi < 1e6) hi *= 2
  if (monthlyBillFromKwh(hi, tranches) < bill) return null
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2
    if (monthlyBillFromKwh(mid, tranches) < bill) lo = mid
    else hi = mid
  }
  return (lo + hi) / 2
}

// QF1 — inverse EXACT du barème : facture mensuelle (MAD TTC) → kWh/mois.
// Miroir kwh_from_bill (analytique si progressif, dichotomie si sélectif).
// Retourne { kwhMensuel, approximatif, estimation }.
export function kwhFromBill(billMad, utility, tranchesOverride) {
  const bill = parseFloat(billMad) || 0
  if (bill <= 0) return { kwhMensuel: 0, approximatif: false, estimation: true }
  const { table, approx } = resolveTranches(utility, tranchesOverride)
  if (!table) {
    return { kwhMensuel: Math.round((bill / FALLBACK_KWH_PRICE) * 10) / 10, approximatif: true, estimation: true }
  }
  if (selectiveRule(table)) {
    const kwh = kwhFromBillBisect(bill, table)
    // ERR-QAH-DIFF-KWH-HORS-PLAGE — même sortie que le serveur : 0 kWh,
    // étiqueté estimation, jamais la borne de boucle présentée comme exacte.
    if (kwh === null) return { kwhMensuel: 0, approximatif: approx, estimation: true }
    return {
      kwhMensuel: Math.round(kwh * 10) / 10,
      approximatif: approx,
      estimation: false,
    }
  }
  let prevCeiling = 0
  let costSoFar = 0
  let kwh = null
  for (const [ceiling, price] of table) {
    if (ceiling == null) { kwh = prevCeiling + (bill - costSoFar) / price; break }
    const trancheCost = (ceiling - prevCeiling) * price
    if (costSoFar + trancheCost >= bill) { kwh = prevCeiling + (bill - costSoFar) / price; break }
    costSoFar += trancheCost
    prevCeiling = ceiling
  }
  if (kwh == null) kwh = prevCeiling + (bill - costSoFar) / table[table.length - 1][1]
  return { kwhMensuel: Math.round(kwh * 10) / 10, approximatif: approx, estimation: false }
}

// ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE — MAD/mois → kWh/mois : l'INVERSE de
// la facture COMPLÈTE (`factureMad` : énergie + lignes fixes + TPPAN), jumeau
// EXACT de `bareme.kwh_depuis_facture_mad` (dichotomie sur le total, mois de
// 30 jours). Un montant qui ne couvre pas les lignes fixes ⇒ 0 kWh ; un montant
// hors plage inversable (au-delà de 1e6 kWh/mois) ⇒ `null` (QJR142 e), jamais
// la borne de boucle.
const PLAFOND_DICHOTOMIE_KWH = 1e6
export function kwhDepuisFactureMad(totalMad, tranches = ONEE_TRANCHES,
  jours = TPPAN_JOURS_REFERENCE) {
  const montant = parseFloat(totalMad) || 0
  if (montant <= 0) return 0
  const total = (k) => factureMad(k, tranches, jours).totalMad
  if (montant <= total(0)) return 0
  let bas = 0
  let haut = 1000
  while (total(haut) < montant && haut < PLAFOND_DICHOTOMIE_KWH) haut *= 2
  if (total(haut) < montant) return null
  for (let i = 0; i < 60; i++) {
    const milieu = (bas + haut) / 2
    if (total(milieu) < montant) bas = milieu
    else haut = milieu
  }
  return Math.round(((bas + haut) / 2) * 10) / 10
}

// Consommation annuelle (kWh/an) DÉRIVÉE des factures mensuelles du client.
// ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE — une facture SAISIE est un TOTAL :
// elle s'inverse avec le barème COMPLET (`kwhDepuisFactureMad`), exactement
// comme le serveur (`etude_horaire.serie_kwh_depuis_mad`, grille NATIONALE —
// tous les distributeurs la lisent, Q7/CAD167), et plus avec l'énergie seule
// (`kwhFromBill`) ni le prix plat 1,20 sans distributeur : l'écran stockait
// jusqu'à ~40 % de kWh en trop sur les petites factures (I9 de COUV-HOR).
// `utility` n'est plus lu (gardé pour la signature des appelants) ;
// `tranchesOverride` = grille vendeur. Un mois non inversable ⇒ 0 (le serveur
// omet toute la série). 0 quand aucune facture exploitable — l'appelant OMET.
export function consoAnnuelleDepuisFactures(factures, utility, tranchesOverride) {
  if (!Array.isArray(factures) || !factures.length) return 0
  const table = tranchesOverride && tranchesOverride.length ? tranchesOverride : ONEE_TRANCHES
  let total = 0
  for (const bill of factures) {
    const kwh = kwhDepuisFactureMad(bill, table)
    if (kwh === null) return 0
    total += kwh
  }
  return total > 0 ? Math.round(total) : 0
}

// L'ANCIENNE dérivation (énergie seule, `kwhFromBill`) — gardée UNIQUEMENT pour
// reconnaître une conso STOCKÉE avant le correctif comme « descendue des
// factures » (`consoDescendDesFactures`), jamais pour en calculer une nouvelle.
function consoAnnuelleEnergieSeule(factures, utility) {
  const total = factures.reduce(
    (somme, bill) => somme + (kwhFromBill(bill, utility).kwhMensuel || 0), 0)
  return total > 0 ? Math.round(total) : 0
}

// COUV-HOR (29/09/2026) — la consommation annuelle STOCKÉE sur un devis
// rouvert DESCEND-ELLE de ses factures stockées (barème du distributeur,
// barème national, ou l'ancien repli factures ÷ 1,20 MAD/kWh) ? Si oui ce
// n'est pas une saisie : l'écran la RE-DÉRIVE des factures au lieu de la
// réafficher comme des kWh tapés puis de la réécrire à l'identique (le
// 165 000 kWh de DEV-202609-0113 revenait à chaque enregistrement). Tolérance
// 12 kWh/an : la dérive ×12 de l'aller-retour kWh/mois (110 000 → 110 004).
export function consoDescendDesFactures(conso, factures, distributeur) {
  const c = parseFloat(conso) || 0
  if (c <= 0 || !Array.isArray(factures) || !factures.length) return false
  const derivee = consoAnnuelleDepuisFactures(factures)
  if (derivee > 0 && Math.abs(c - derivee) <= 12) return true
  for (const d of new Set([distributeur || undefined, 'onee', undefined])) {
    const ancienne = consoAnnuelleEnergieSeule(factures, d)
    if (ancienne > 0 && Math.abs(c - ancienne) <= 12) return true
  }
  return false
}

// ════════════════════════════════════════════════════════════════════════════
// QJR168 — LE BARÈME COMPLET : UNE FACTURE N'EST PAS QUE DE L'ÉNERGIE
// ════════════════════════════════════════════════════════════════════════════
// Jumeau JS de apps/ventes/quote_engine/bareme.py, le module étalonné sur TROIS
// FACTURES RÉELLES du fondateur (SRM Casablanca-Settat, BT domestique) et qui
// reproduit la facture du 08/05/2026 à 0,01 MAD près. Le serveur tarife les
// deux factures du modèle « deux factures » par `bareme.facture_mad` depuis
// QJR157 ; l'écran, lui, était resté sur l'énergie seule — le même client
// lisait donc deux « factures actuelles » différentes selon qu'il regardait
// l'écran (24 343 MAD/an) ou le PDF (26 022 MAD/an). QJR168 referme l'écart en
// portant ici le MÊME modèle, pas en ajustant un chiffre.
//
// CHAQUE NOMBRE VIENT DE bareme.py — aucun n'est estimé :
//   · location du compteur     18,28 MAD HT/mois (montant identique sur les
//     trois factures) ; entretien du branchement 15,00 MAD HT/mois (idem) ;
//     TVA 20 % sur les deux en 2026 → 39,936 MAD TTC/mois, soit 479,23 MAD/an ;
//   · TPPAN (art. 16 du dahir n° 1-96-77, BO 4391 bis) : empilement PROGRESSIF
//     0,10 / 0,15 / 0,20, bornes 100 et 200 kWh proratisées aux jours de la
//     période, plafond 100 MAD/mois, exonération ≤ 50 kWh/mois. Le barème 1996
//     produit directement un montant TTC — prouvé par la facture du 08/05/2026
//     (100 × 0,10 + 100 × 0,15 + 159 × 0,20 = 56,80, la ligne exacte).
// MILLÉSIME : 2026, celui d'ONEE_TRANCHES. Le serveur en gère plusieurs (2025
// avait trois taux de TVA différents sur une même facture) ; l'écran ne tarife
// que la grille qu'il affiche.
//
// CE QUI S'ANNULE, CE QUI NE S'ANNULE PAS : les deux lignes fixes sont dues
// avec ou sans solaire — elles disparaissent donc de l'ÉCONOMIE (le client
// garde son abonnement ; les lui compter serait un mensonge) mais elles pèsent
// sur les deux FACTURES affichées. La TPPAN, elle, suit le kWh : elle baisse
// avec la consommation et fait partie de l'économie réelle.
const CHARGE_LOCATION_COMPTEUR_HT = 18.28
const CHARGE_ENTRETIEN_BRANCHEMENT_HT = 15.00
const TVA_LIGNES_FIXES = 0.20            // millésime 2026 (location ET entretien)
const TPPAN_TRANCHES = [[100, 0.10], [200, 0.15], [null, 0.20]]
const TPPAN_JOURS_REFERENCE = 30
const TPPAN_PLAFOND_MAD_MOIS = 100
const TPPAN_EXONERATION_KWH_MOIS = 50

// Total TTC des DEUX lignes fixes d'un mois : 18,28 × 1,20 + 15,00 × 1,20
// = 39,936 MAD. (bareme.charges_fixes_ttc, millésime 2026.)
export function chargesFixesTtc() {
  return CHARGE_LOCATION_COMPTEUR_HT * (1 + TVA_LIGNES_FIXES)
    + CHARGE_ENTRETIEN_BRANCHEMENT_HT * (1 + TVA_LIGNES_FIXES)
}

// ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — contrôle des 12 factures que
// l'écran s'apprête à enregistrer comme « réelles ». DEV-202609-0108 est parti
// au client avec `estimerMois(1, 1600)` (hiver 1 MAD/mois, sous les lignes
// fixes du compteur) alors que son lead disait 3 000 MAD d'hiver.
//   · `sousPlancher` : mois (1-12) dont la facture est > 0 mais sous
//     `chargesFixesTtc()` — impossible pour une vraie facture (le serveur,
//     `domain/etude_schema.py`, refuse la même série) ;
//   · `ecartLead` : la facture de janvier (le mois d'HIVER de `estimerMois`)
//     s'écarte de plus de 25 % de la facture d'hiver du lead ⇒
//     `{ serie, lead }`, à faire CONFIRMER, jamais corrigé en silence.
export const ECART_FACTURE_LEAD_MAX = 0.25
export function controlerFacturesSaisies(factures, { factureHiverLead } = {}) {
  const plancher = chargesFixesTtc()
  const serie = Array.isArray(factures) ? factures.map(v => Number(v) || 0) : []
  const sousPlancher = []
  serie.forEach((v, i) => { if (v > 0 && v < plancher) sousPlancher.push(i + 1) })
  const lead = Number(factureHiverLead) || 0
  let ecartLead = null
  if (lead > 0 && serie.length === 12 && serie[0] > 0
      && Math.abs(serie[0] - lead) / lead > ECART_FACTURE_LEAD_MAX) {
    ecartLead = { serie: serie[0], lead }
  }
  return { plancher, sousPlancher, ecartLead }
}

// ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — jumeau de
// etude_horaire.coherence_kwh_declare_factures (décision fondateur 30/09/2026).
// Le kWh mensuel DÉCLARÉ sur la fiche du lead prime sur ses factures (Q14,
// CAD166) SEULEMENT s'il est vraisemblable : facture_barème(kWh) ÷ facture
// déclarée doit tomber dans [0,5 ; 2] pour AU MOINS une facture déclarée
// (hiver, et été quand elle est distincte). Sinon l'enregistrement est REFUSÉ.
// `null` quand rien n'est confrontable (kWh ou facture absents).
const RATIO_KWH_FACTURE_MIN = 0.5
const RATIO_KWH_FACTURE_MAX = 2
export const MESSAGE_KWH_INCOHERENT =
  'kWh déclarés incohérents avec les factures — corriger la fiche du lead'
export function controlerKwhDeclare(kwhMensuel, { factureHiver, factureEte, eteDifferente } = {},
  tranches = ONEE_TRANCHES) {
  const kwh = parseFloat(kwhMensuel) || 0
  const factures = [factureHiver, eteDifferente ? factureEte : null]
    .map(v => parseFloat(v) || 0).filter(v => v > 0)
  if (!(kwh > 0) || !factures.length) return null
  const factureBareme = factureMad(kwh, tranches).totalMad
  const ratios = factures.map(f => factureBareme / f)
  return {
    factureBareme,
    ratios,
    coherent: ratios.some(r => r >= RATIO_KWH_FACTURE_MIN && r <= RATIO_KWH_FACTURE_MAX),
  }
}

// TPPAN TTC due sur une période de `jours` jours consommant `kwhMensuel`.
// Jumeau de bareme.tppan_mad : empilement progressif sur la TOTALITÉ de la
// consommation, bornes proratisées, plafonné. Monotone non décroissante.
export function tppanMad(kwhMensuel, jours = TPPAN_JOURS_REFERENCE) {
  const kwh = parseFloat(kwhMensuel) || 0
  if (kwh <= 0 || kwh <= TPPAN_EXONERATION_KWH_MOIS) return 0
  let ratio = (parseFloat(jours) || TPPAN_JOURS_REFERENCE) / TPPAN_JOURS_REFERENCE
  if (!(ratio > 0)) ratio = 1
  let total = 0
  let restant = kwh
  let borneBasse = 0
  for (const [plafond, prix] of TPPAN_TRANCHES) {
    if (plafond == null) { total += restant * prix; break }
    const borneHaute = plafond * ratio
    const tranche = Math.min(restant, Math.max(0, borneHaute - borneBasse))
    total += tranche * prix
    restant -= tranche
    borneBasse = borneHaute
    if (restant <= 0) break
  }
  return Math.min(total, TPPAN_PLAFOND_MAD_MOIS)
}

// kWh/mois → facture mensuelle TTC DÉTAILLÉE (MAD), composante par composante,
// dans l'ordre de la vraie facture. Jumeau de bareme.facture_mad. Une
// consommation nulle ne doit RIEN en énergie ni en TPPAN, mais les lignes
// fixes restent dues : c'est la réalité d'un abonnement.
export function factureMad(kwhMensuel, tranches, jours = TPPAN_JOURS_REFERENCE) {
  const kwh = parseFloat(kwhMensuel) || 0
  const energie = kwh > 0 ? monthlyBillFromKwh(kwh, tranches) : 0
  const fixes = chargesFixesTtc()
  const taxe = tppanMad(kwh, jours)
  return {
    energieMad: energie,
    locationEntretienMad: fixes,
    tppanMad: taxe,
    totalMad: energie + fixes + taxe,
  }
}

// QF2 — modèle « deux factures » : économie = facture_sans − facture_avec,
// valorisée par tranche (self-consumption-first, loi 82-21). Jumeau de
// two_bills_savings. Retourne null quand une vraie donnée manque (l'appelant
// dégrade alors vers l'estimation, jamais un chiffre inventé).
// QJR168 — les deux factures passent par `factureMad` (lignes fixes + TPPAN),
// comme le serveur depuis QJR157 : le mois reste l'unité de tarification (le
// seuil des marches est MENSUEL), on ne divise jamais l'année après avoir
// tarifé. Mois MOYEN, comme le repli serveur sans répartition mensuelle.
export function twoBillsSavings(productionKwh, consoAnnuelleKwh, autoconsoRatio, utility, tranchesOverride) {
  const { table } = resolveTranches(utility, tranchesOverride)
  if (!table) return null
  const conso = parseFloat(consoAnnuelleKwh) || 0
  const prod = parseFloat(productionKwh) || 0
  const ratio = parseFloat(autoconsoRatio) || 0
  if (conso <= 0 || prod <= 0 || ratio <= 0) return null
  const factureAnnuelle = (consoAn) => factureMad(consoAn / 12, table).totalMad * 12
  const factureSans = Math.round(factureAnnuelle(conso))
  const autoconsoKwh = Math.min(prod * ratio, conso)
  const residuel = Math.max(0, conso - autoconsoKwh)
  const factureAvec = Math.round(factureAnnuelle(residuel))
  return {
    factureSans, factureAvec,
    economie: Math.max(0, factureSans - factureAvec),
    autoconsoKwh: Math.round(autoconsoKwh),
  }
}
