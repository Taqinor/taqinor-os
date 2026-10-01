/* Création du « devis automatique » — logique PARTAGÉE entre le générateur
   complet (DevisGenerator) et le panneau devis inline de la fiche lead
   (LeadDevisPanel). Source unique : on ne duplique JAMAIS le calcul de prix.

   Sensible au marché du lead : résidentiel (historique), agricole (pompage,
   mêmes appels que le flux manuel) ou industriel (dimensionnement factures +
   étude d'autoconsommation). Lit le lead directement (pas d'état React). */
// QJR543 — plus de createDevis + N addLigneDevis : les marchés non
// résidentiels se créent en UN appel atomique (POST /ventes/devis/atomic/).
// QJR542 — l'étude part par LA projection partagée avec le générateur.
import { projeterEtudeMarche } from './quote/etudeMarcheBloc'
// U3 — le devis résidentiel auto est COMPOSÉ ET CRÉÉ par le serveur
// (POST /ventes/devis/auto/) : cet écran ne compose plus de lignes
// résidentielles. Voir la branche `mode === 'residentiel'` plus bas.
import ventesApi from '../../api/ventesApi'
import {
  estimerMois, htFromTtc, ttcFromHt, optionTotalsTTC,
  autoFillLines, computeEtudeIndustrielle, panneauxPourKwc,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  KWH_PRICE, EFFICIENCY, DAY_USAGE_DEFAULTS,
  // Règle fondateur du 18/08 — dimensionnement AUTOMATIQUE (sans cible) par
  // PALIERS de 5 kWc, retenus au payback le plus court. QJR602 : une taille
  // explicite n'est plus jamais ramenée au palier (D-QJR5-13).
  estimerKwcDepuisFacture, optimalKwcByPayback,
  // PVMRQ — libellé FR d'un rôle, pour dire QUELLE marque épinglée manque.
  roleLabel,
  // PACT10/QF-REAL — consommation annuelle RÉELLE du lead, dérivée de ses
  // factures par l'inverse EXACT du barème (`kwhFromBill`, QF4). UNE seule
  // dérivation partagée : elle alimente à la fois le balayage de
  // dimensionnement (sans elle, l'économie ne sature pas) et
  // `etude_params.conso_annuelle` envoyée au serveur.
  // ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — le balayage chiffre la production
  // au productible de la VILLE (comme l'aperçu et le PDF), jamais au repli
  // historique GHI × 0,8 de `computeROI` (≈ −18 % contre le document).
  productibleForCity,
  // QJR575 — part diurne d'une catégorie commerciale (80 % pour une clé
  // inconnue ou absente : la sentinelle « Non précisée » de l'écran).
  commercialDayShare,
  // QJR576 — UNE conversion panneaux ↔ kWc et UN wattage par défaut.
  kwcPourPanneaux, PANEL_W_DEFAUT,
  // QJR603 — facture mensuelle que le barème national associe à des kWh
  // (inverse exact de `consoAnnuelleDepuisFactures`).
  factureMad, ONEE_TRANCHES,
  consoAnnuelleDepuisFactures,
} from './solar'
// QJR576 — le vocabulaire des scénarios et le mapping lead → scénario
// viennent du reducer (jamais retapés ici).
import {
  SCENARIO_SANS, SCENARIO_LES_DEUX, BATTERIE_LEAD_VERS_SCENARIO,
} from './quote/sizingReducer'

// QJR575 — LES PARAMÈTRES DU BALAYAGE C&I, UNE SEULE CONSTRUCTION pour le
// « Devis automatique » (ci-dessous) ET l'Édition complète (DevisGenerator,
// `computeAutoSizing`) : sans elle, les deux boutons dimensionnaient le même
// lead à deux kWc (modèle 'factures' via le défaut d'écran 'onee' contre
// modèle 'estimation' ici ; hôtel 55 % contre 80 %).
//   • part diurne : commercial → `commercialDayShare(categorie)` (80 % sans
//     catégorie) ; industriel / résidentiel → DAY_USAGE_DEFAULTS ;
//   • `utility` (modèle d'économie) : le distributeur DÉCLARÉ (choisi par le
//     vendeur, sinon celui du lead) s'il est l'un des trois barèmes connus,
//     sinon `undefined` — jamais un défaut d'écran (mémoire
//     ci-autoquote-conso-only : le modèle d'économie reste celui d'avant) ;
//   • conso : la consommation RÉELLE saisie si elle existe, sinon les
//     factures au barème (national par défaut, COUV-HOR — jamais ÷ 1,20).
export function parametresBalayageCI({
  factures, mode, categorie, distributeurDeclare, consoAnnuelleReelle,
} = {}) {
  const dayUsagePct = mode === 'commercial' ? commercialDayShare(categorie)
    : mode === 'industriel' ? DAY_USAGE_DEFAULTS['Industrielle']
      : DAY_USAGE_DEFAULTS['Résidentielle']
  const utility = ['onee', 'lydec', 'redal'].includes(distributeurDeclare)
    ? distributeurDeclare : undefined
  const consoAnnuelleKwh = Number(consoAnnuelleReelle) > 0
    ? Number(consoAnnuelleReelle)
    : consoAnnuelleDepuisFactures(factures, utility || 'onee')
  return { factures, dayUsagePct, consoAnnuelleKwh, utility }
}

// QJR665 (décision fondateur 01/10 — barème national pour les deux) — la
// consommation MENSUELLE de l'étude C&I (taux d'autoconsommation, économies,
// payback) tirée des factures : celle du balayage qui choisit le kWc
// (`parametresBalayageCI`, barème national COUV-HOR) ÷ 12, non arrondie (la
// conso annuelle imprimée redonne celle du balayage). Jamais moyenne des
// factures ÷ kwhPrice. 0 sans facture exploitable. Partagée par le devis
// automatique et l'Édition complète ; une conso saisie reste prioritaire chez
// l'appelant.
export function consoMensuelleEtudeCI({ factures, mode, distributeurDeclare } = {}) {
  if (!Array.isArray(factures) || !factures.length) return 0
  const { consoAnnuelleKwh } = parametresBalayageCI({ factures, mode, distributeurDeclare })
  return consoAnnuelleKwh > 0 ? consoAnnuelleKwh / 12 : 0
}

// QJR603 (D-QJR5-14) — kWh MENSUELS d'un lead pro : `conso_mensuelle_kwh`
// (champ éditable), sinon `bill_kwh` (tunnel du site) — la MÊME porte que le
// serveur (`apps/crm/devis_auto.py`, groupe « l'un des » de CAD166). 0 sans
// donnée exploitable. Un lead pro SANS facture d'hiver exploitable se
// dimensionne par le balayage C&I existant depuis ces kWh : consommation =
// kWh mensuels × 12, factures = celles que le barème national associe à ces
// kWh (`factureMad`, l'inverse exact de `consoAnnuelleDepuisFactures`),
// besoin = la règle des paliers lue sur cette facture. Aucun coefficient
// nouveau ; un lead qui porte une facture d'hiver garde le balayage de sa
// facture, inchangé.
export const kwhMensuelsLeadPro = (lead) =>
  (parseFloat(lead?.conso_mensuelle_kwh) || 0) || (parseFloat(lead?.bill_kwh) || 0)

// QX19 — préférence de structure du lead (acier/aluminium) → structureType
// d'autoFillLines/autoFillPompage. Défaut historique 'acier' quand non renseigné.
const structFromLead = (lead) =>
  (lead && lead.structure_pref === 'aluminium') ? 'aluminium' : 'acier'

/* STKCAT10 — LE PRODUIT DE STRUCTURE ÉPINGLÉ SUR LE LEAD (`structure_produit`,
   STKCAT9 : id `stock.Produit`, écrit depuis la fiche lead). Il PRIME sur la
   préférence acier/alu partout où cet écran compose LUI-MÊME les lignes —
   c'est-à-dire l'agricole (pompage) et l'industriel/commercial, les trois
   marchés qui n'ont AUCUN dry-run serveur.

   LE RÉSIDENTIEL, LUI, NE L'ENVOIE PAS — ET C'EST VOLONTAIRE : sa création
   part à `POST /ventes/devis/auto/`, qui ne lit PAS `structure_produit_id`
   dans le corps et résout la structure DEPUIS LE LEAD lui-même
   (`apps/ventes/domain/creation.py::_structure_demandee`, STKCAT9 : id épinglé
   → préférence acier/alu → acier). Le renvoyer ici le dupliquerait sans rien
   changer, et créerait une seconde source de vérité à faire diverger. */
const structProduitFromLead = (lead) => {
  const id = lead?.structure_produit
  return (id === null || id === undefined || id === '') ? undefined : String(id)
}

// ERR107 — Cohérence d'arrondi écran : une ligne est ENREGISTRÉE en HT 2 déc.
// (htFromTtc), donc le TTC RÉAFFICHÉ d'une ligne est ttcFromHt(htFromTtc(ttc)),
// qui peut différer du TTC brut saisi d'1 MAD. Pour que le total d'étude affiché
// à l'écran corresponde exactement à la somme des lignes telles que l'écran les
// recompose, on aligne d'abord chaque prix_unit_ttc sur ce même aller-retour.
// (Écran uniquement — le PDF backend recalcule de façon autoritaire.)
const screenTtc = (r) => ttcFromHt(htFromTtc(r.prix_unit_ttc, r.taux_tva ?? 20), r.taux_tva ?? 20)
const roundTripRowsTtc = (rows) => rows.map((r) => ({ ...r, prix_unit_ttc: screenTtc(r) }))

// QX52 — parité 4 modes : `commercial` route désormais vers son PROPRE mode
// (plus le repli historique vers `industriel`). Aucun mode ne tombe dans un
// libellé/comportement d'un autre.
export const LEAD_TYPE_TO_MODE = {
  residentiel: 'residentiel', commercial: 'commercial',
  industriel: 'industriel', agricole: 'agricole',
}

// Paramètres d'étude pompage stockés avec le devis : chiffres canoniques
// calculés UNE fois, le PDF les rend tels quels. Partagé entre la création
// manuelle (DevisGenerator.handleSubmit) et le devis auto — mêmes expressions.
export const buildEtudePompage = (sel, { typePompe, alim, hmt, debit, heures,
                                         profondeur, distance }) => ({
  pompe_cv: String(sel.cv),
  pompe_kw: sel.kw,
  pompe_nom: sel.pump?.nom || null,
  type_pompe: typePompe,
  alim,
  hmt_m: hmt || null,
  debit_souhaite_m3h: debit || null,
  debit_hmt_m3h: sel.debitHmt,
  heures_pompage: sel.m3Jour != null ? (parseFloat(heures) || null) : null,
  m3_jour: sel.m3Jour,
  profondeur_m: profondeur || null,
  distance_m: distance || null,
  champ_kwc: sel.dims.champKwc,
})

/**
 * QJR602 (D-QJR5-13) — PLUS AUCUN PALIER N'EST APPLIQUÉ À UNE TAILLE
 * EXPLICITE : il n'y a donc plus rien à annoncer, la fonction rend toujours
 * `null`. Elle ne subsiste que pour ses deux derniers appelants, hors de ce
 * lot : le générateur (`DevisGenerator.jsx`, `runAutoQuote`) et
 * `LeadDevisPanel.jsx` — à supprimer avec leurs imports.
 */
export function noticePalierKwc() {
  return null
}

/**
 * Crée un devis auto-dimensionné depuis un lead. Retourne l'id du devis créé.
 * Lève { detail } si le lead n'a pas les données requises (mêmes règles que la
 * garde serveur POST /devis-auto/).
 *
 * @param {object}   lead         Lead complet (facture_hiver, pompe_*, etc.)
 * @param {object[]} produits     Catalogue stock
 * @param {string}   discountStr  Remise globale en %
 * @param {function} dispatch     (ignoré depuis QJR543 — création atomique via ventesApi)
 * @param {number}   pumpHours    Heures de pompage/jour (réglage entreprise
 *                                agricole_pump_hours) ; défaut historique sinon
 * @param {function} onEtude      Rappel facultatif recevant les chiffres clés de
 *                                l'étude industrielle (autoconso/éco/payback)
 *                                AVANT enregistrement — pour les afficher
 * @param {string|number} targetKwc  EZ5 — puissance cible (kWc) demandée POUR
 *                                CE devis-là, sans toucher la fiche du lead.
 *                                Vide/absent = comportement historique (la
 *                                taille souhaitée du lead, sinon la facture).
 * @param {object}   marques      PVMRQ — marques préférées par rôle (gamme
 *                                active, `ParametresGammes.marques[slot]`) ;
 *                                transmise telle quelle à `optimalKwcByPayback`
 *                                et `autoFillLines`. Absente/vide = comportement
 *                                historique (aucune préférence).
 * @param {string[]} ordreLignes  PVORD (fondateur 19/08/2026) — ordre par
 *                                défaut des lignes (`ParametresGammes.
 *                                ordre_lignes`), transmis tel quel à
 *                                `autoFillLines`. Absente/vide = ordre
 *                                canonique du simulateur (comportement
 *                                historique).
 */
export async function createAutoQuote({ lead, produits, discountStr,
                                        quoteLogic, pumpHours, onEtude,
                                        targetKwc, marques, ordreLignes }) {
  // Logique de devis éditable (Paramètres → Avancé) ; sans valeur = défauts.
  const kwhPrice = (Number(quoteLogic?.kwhPrice) > 0) ? Number(quoteLogic.kwhPrice) : KWH_PRICE
  const efficiency = (Number(quoteLogic?.efficiency) > 0) ? Number(quoteLogic.efficiency) : EFFICIENCY
  // U3-900 — la règle des 900 DH/mois (ex-`panneauxParTranche`) a été
  // supprimée (fondateur 29/08/2026) : le réglage qui l'alimentait
  // (`panneaux_par_900mad`) a lui-même été retiré du modèle et de l'écran
  // Paramètres → Avancé — plus aucun consommateur.
  // Heures de pompage effectives : réglage entreprise (agricole_pump_hours) si
  // fourni, sinon le défaut marché historique — comme le générateur manuel.
  const heuresPompage = (Number(pumpHours) > 0) ? Number(pumpHours) : HEURES_POMPAGE_DEFAUT
  const mode = LEAD_TYPE_TO_MODE[lead.type_installation] || 'residentiel'
  const extra = {}
  let rows
  if (mode === 'agricole') {
    const opts = {
      cv: lead.pompe_cv != null ? String(lead.pompe_cv) : '',
      alim: 'tri', typePompe: 'immergee', distance: '20',
      // QX19 — respecte la préférence de structure du lead (défaut acier).
      structureType: structFromLead(lead),
      // STKCAT10 — …et le PRODUIT épinglé prime dessus quand il existe.
      structureProduitId: structProduitFromLead(lead),
      hmt: lead.pompe_hmt_m != null ? String(lead.pompe_hmt_m) : '',
      debit: lead.pompe_debit_m3h != null ? String(lead.pompe_debit_m3h) : '',
      heures: String(heuresPompage),
    }
    rows = autoFillPompage(produits, opts)
    if (!rows.some(r => r.produit && parseFloat(r.quantite) > 0)) {
      throw {
        detail: 'Devis auto impossible : renseignez sur le lead la puissance '
          + 'pompe (CV) ou la HMT et le débit souhaité, puis réessayez.',
      }
    }
    extra.mode_installation = 'agricole'
    // QJR543 — l'objet BRUT de `buildEtudePompage` porte des clés hors
    // schéma (pompe_nom) : il passe par LA projection du générateur (QJR542),
    // qui ne laisse sortir que des clés ECRAN typées.
    extra.etude_params = projeterEtudeMarche('agricole', {
      choix: {},
      entrees: {},
      pompage: buildEtudePompage(
        pompageSelection(produits, opts), { ...opts, profondeur: '' }),
      saisiePompage: {
        hmt: opts.hmt, debit: opts.debit, heures: opts.heures,
        typePompe: opts.typePompe, alim: opts.alim,
        profondeur: '', distance: opts.distance,
      },
    })
  } else {
    const hiver = parseFloat(lead.facture_hiver) || 0
    // QX19 — priorité à la taille souhaitée par le lead (kWc) quand elle est
    // renseignée ; sinon dérivation depuis la facture d'hiver. EZ5 — une cible
    // saisie POUR CE DEVIS (« Devis automatique » de la fiche lead) passe
    // devant les deux : c'est un choix ponctuel du commercial, il ne réécrit
    // jamais `taille_souhaitee_kwc` sur le lead. Même conversion partagée
    // `panneauxPourKwc` — aucune formule recopiée.
    // QJR602 (D-QJR5-13, fondateur 30/09/2026) — une taille EXPLICITE (cible
    // du devis ou taille souhaitée du lead) est SOUVERAINE, telle quelle : plus
    // d'arrondi au palier de 5 kWc (6,5 kWc → 10 panneaux de 710 W, le même
    // compte que le serveur — `taille.py::_residential_panel_count`). Les
    // paliers ne servent qu'au dimensionnement AUTOMATIQUE sans cible : le
    // besoin se lit alors sur la facture d'hiver (`estimerKwcDepuisFacture`)
    // et la taille retenue est le palier au payback le plus court
    // (`optimalKwcByPayback`).
    const cibleKwc = parseFloat(targetKwc) || 0
    const tailleKwc = cibleKwc > 0 ? cibleKwc : (parseFloat(lead.taille_souhaitee_kwc) || 0)
    let panels = 0
    if (tailleKwc > 0) {
      panels = panneauxPourKwc(tailleKwc, PANEL_W_DEFAUT)
    } else if (mode !== 'residentiel') {
      // U3-MOTEUR (fondateur 29/08/2026, « ALL sizing goes through the new
      // sizing tool ») — LE BALAYAGE LOCAL PAR PALIERS N'EST PLUS LA SOURCE DE
      // DIMENSIONNEMENT DU RÉSIDENTIEL. C'était le dernier contournement : au
      // -dessus du seuil de facture, cet écran chiffrait lui-même les paliers
      // de 5 kWc (`optimalKwcByPayback`) et expédiait le résultat en
      // `target_kwc` SOUVERAIN — ces devis-là ne touchaient jamais le moteur
      // horaire (PVGIS × consommation réelle heure par heure), donc deux
      // méthodes de dimensionnement coexistaient selon le montant de la
      // facture. Désormais, en résidentiel, `panels` reste à 0 : `target_kwc`
      // est OMIS plus bas et c'est `build_devis_auto` (moteur horaire) qui
      // dimensionne — ou refuse en NOMMANT la donnée manquante.
      // Une taille EXPLICITE (cible tapée pour ce devis, ou `taille_souhaitee_kwc`
      // du lead) reste SOUVERAINE : elle est traitée par la branche ci-dessus,
      // avant celle-ci, et part telle quelle. Seule la valeur AUTO-CALCULÉE
      // cesse d'être expédiée.
      // Industriel/commercial gardent ce balayage : aucun moteur serveur ne
      // les dimensionne (`build_devis_auto` ne gère que le résidentiel), et
      // sans lui ils n'auraient plus AUCUNE taille (voir le refus explicite
      // plus bas).
      // QJR603 — lead pro « kWh seulement » : voir `kwhMensuelsLeadPro`.
      const besoinFacture = estimerKwcDepuisFacture(hiver)
      const kwhMois = besoinFacture > 0 ? 0 : kwhMensuelsLeadPro(lead)
      const factureKwh = kwhMois > 0 ? factureMad(kwhMois, ONEE_TRANCHES).totalMad : 0
      const besoinKwc = besoinFacture > 0 ? besoinFacture : estimerKwcDepuisFacture(factureKwh)
      if (besoinKwc > 0) {
        const eteVal = (lead.ete_differente && lead.facture_ete)
          ? parseFloat(lead.facture_ete) : hiver
        // FINDING 25/08 — la CONSOMMATION RÉELLE entre dans le balayage. Sans
        // elle, `computeROI` ne plafonne pas l'économie à ce que le client
        // peut consommer : elle reste linéaire en kWc, chaque pas marginal se
        // « rembourse » et l'ascension ne s'arrête qu'au plafond du balayage
        // (mesuré : besoin 100 kWc → 100 kWc retenus, 522 341 MAD). C'est la
        // MÊME dérivation que `etude_params.conso_annuelle` posée plus bas —
        // désormais partagée (`consoAnnuelleDepuisFactures`), donc impossible
        // à faire diverger entre le dimensionnement et l'étude envoyée.
        // QJR575 — MÊMES paramètres que l'Édition complète. Aucune catégorie
        // commerciale n'est lue du lead (NE PAS FAIRE) : 80 % par défaut.
        const balayage = parametresBalayageCI({
          factures: kwhMois > 0 ? Array(12).fill(factureKwh) : estimerMois(hiver, eteVal),
          mode,
          distributeurDeclare: lead.distributeur,
          consoAnnuelleReelle: kwhMois > 0 ? kwhMois * 12 : undefined,
        })
        const opt = optimalKwcByPayback({
          produits, factures: balayage.factures, dayUsagePct: balayage.dayUsagePct,
          panelW: PANEL_W_DEFAUT, structureType: structFromLead(lead),
          // STKCAT10 — le balayage chiffre chaque palier avec LA structure
          // réellement retenue (produit épinglé s'il existe), jamais une autre.
          structureProduitId: structProduitFromLead(lead),
          discountPct: discountStr || '0', kwhPrice, efficiency, besoinKwc,
          marques,
          // COUV-HOR (fondateur, 29/09/2026) — la CONSO du balayage suit le
          // barème national (Q7), jamais factures ÷ 1,20 MAD/kWh ; le MODÈLE
          // d'économie (`utility`) reste celui d'avant — décision fondateur :
          // 0 devis C&I sur 61 ne bouge (mesuré sur la prod le 29/09).
          consoAnnuelleKwh: balayage.consoAnnuelleKwh,
          utility: balayage.utility,
          productible: productibleForCity(lead.ville || '', quoteLogic?.productible),
        })
        // U3-900 (fondateur 29/08/2026) — plus de repli `estimerPanneaux`
        // (panneaux/900 MAD, supprimé du backend le même jour). `panels`
        // reste à 0 quand l'optimiseur local n'a rien retenu : sur ces
        // marchés (industriel/commercial) c'est un refus EXPLICITE plus bas,
        // jamais une taille devinée sur une règle qui n'existe plus.
        panels = opt.nbPanneaux > 0 ? opt.nbPanneaux : 0
      }
      // besoinKwc <= 0 (facture sous le seuil du balayage local) : `panels`
      // reste à 0, MÊME raison — voir la note ci-dessus.
    }
    // U3-900 — un `panels` nul n'est PAS une composition « à 0 panneau » : en
    // résidentiel il veut dire « le serveur dimensionne » (target_kwc omis
    // plus bas) ; pour les autres marchés (aucun moteur serveur pour eux),
    // c'est un vrai refus explicite plus bas — jamais un devis vide créé en
    // silence.
    const kwpAuto = panels > 0 ? kwcPourPanneaux(panels, PANEL_W_DEFAUT) : 0

    // ── U3 (fondateur 20/08/2026) — LE RÉSIDENTIEL NE COMPOSE PLUS ICI ─────
    // Ordre fondateur APPLIQUÉ par ce fichier : la composition n'a plus
    // qu'UNE source de vérité (le serveur) et cet écran la consomme.
    //
    // Il y en avait bien deux : cet écran composait le kit en JavaScript
    // (`autoFillLines`) pendant que le serveur le composait en Python
    // (`composition_residentielle`) — et les deux avaient divergé sur le
    // câble au mètre, les marques épinglées, l'ordre des lignes et l'arrondi
    // du nombre de panneaux. Désormais le devis résidentiel auto part au
    // serveur avec la SEULE chose que l'écran a décidée — la PUISSANCE CIBLE
    // — et c'est le serveur qui compose ET crée les lignes : catalogue,
    // ordre (PVORD), marques épinglées (PVMRQ), câble au mètre × paires (C4),
    // scénario batterie (U2). Aucune ligne, aucun prix, aucune marque ne
    // remonte d'ici : il n'y a plus rien à faire diverger.
    //
    // Ce qui reste À L'ÉCRAN est le DIMENSIONNEMENT (le balayage par palier
    // au payback le plus court ci-dessus) et l'étude PACT10 : ce sont des
    // décisions commerciales, pas une composition — elles voyagent en
    // paramètres, jamais en lignes.
    if (mode === 'residentiel') {
      const etudeExtra = {}
      // PACT10/QF-REAL — les 12 factures RÉELLES du client (et la
      // consommation annuelle qui s'en déduit) : sans elles, le PDF
      // reconstruit les « factures avant » depuis l'économie SUPPOSÉE, un
      // proxy circulaire. Le `scenario`, lui, n'est PLUS envoyé d'ici : le
      // serveur le décide depuis `lead.batterie_souhaitee` (défaut « les
      // deux » — U2), sinon on recréerait à l'instant la divergence qu'on
      // vient de supprimer.
      if (hiver > 0) {
        const eteReel = (lead.ete_differente && lead.facture_ete)
          ? parseFloat(lead.facture_ete) : hiver
        const facturesReelles = estimerMois(hiver, eteReel)
        const distributeurLead = ['onee', 'lydec', 'redal'].includes(lead.distributeur)
          ? lead.distributeur : undefined
        // Dérivation PARTAGÉE avec le dimensionnement ci-dessus (le balayage
        // par palier a besoin de la MÊME consommation pour que son modèle
        // d'économie sature) — une seule formule, jamais deux chiffres qui
        // pourraient diverger.
        // COUV-HOR — barème NATIONAL (Q7) même sans distributeur connu : jamais
        // factures ÷ 1,20 MAD/kWh (DEV-202609-0113 : 165 000 kWh au lieu de 122 007).
        const consoAnnuelleReelle = consoAnnuelleDepuisFactures(
          facturesReelles, distributeurLead || 'onee')
        etudeExtra.factures_mensuelles_reelles = facturesReelles
        if (consoAnnuelleReelle > 0) etudeExtra.conso_annuelle = consoAnnuelleReelle
        if (distributeurLead) etudeExtra.distributeur = distributeurLead
      }
      let reponse
      try {
        reponse = await ventesApi.creerDevisAuto({
          lead: lead.id,
          remise_globale: discountStr || '0',
          // STKCAT10 — AUCUN `structure_produit_id` ici, DÉLIBÉRÉMENT :
          // `POST /ventes/devis/auto/` ne le lit pas dans le corps et résout
          // la structure depuis le LEAD (`_structure_demandee`, STKCAT9).
          // L'envoyer serait une seconde source de vérité pour rien.
          // U3-MOTEUR — `kwpAuto` ne peut plus venir ici que d'une taille
          // EXPLICITEMENT choisie par un humain (cible tapée pour ce devis, ou
          // `taille_souhaitee_kwc` du lead) : elle reste souveraine et le
          // serveur en redérive le MÊME nombre de panneaux (plafond tolérant
          // au flottant, verrouillé des deux côtés par un test d'aller-retour).
          // Sans taille explicite, `kwpAuto` vaut 0 et `target_kwc` est OMIS :
          // c'est le moteur horaire de `build_devis_auto` qui dimensionne (et
          // refuse en nommant la donnée manquante) — plus AUCUNE puissance
          // auto-calculée côté écran n'est expédiée.
          ...(kwpAuto > 0 ? { target_kwc: kwpAuto } : {}),
          ...(Object.keys(etudeExtra).length ? { etude_params: etudeExtra } : {}),
        })
      } catch (err) {
        // Le serveur parle FRANÇAIS (422 : marque épinglée introuvable,
        // données de dimensionnement manquantes…) et ses appelants lisent
        // `err.detail` — on rend son message tel quel, jamais un nôtre.
        throw {
          detail: err?.response?.data?.detail
            || "Le devis automatique a échoué — vérifiez la fiche du lead et réessayez.",
        }
      }
      const id = reponse?.data?.id
      if (!id) {
        throw { detail: 'Devis créé sans identifiant — ouvrez-le depuis la liste des devis.' }
      }
      return id
    }

    // U3-900 (fondateur 29/08/2026) — industriel/commercial n'ont AUCUN
    // moteur serveur pour se dimensionner eux-mêmes ici (celui de
    // `build_devis_auto` ne gère que le résidentiel) : sans `estimerPanneaux`
    // pour deviner une taille (supprimé), un `panels` toujours nul créerait
    // silencieusement un devis SANS panneau. On refuse explicitement à la
    // place — même idiome que la garde agricole plus haut — plutôt que de
    // laisser passer un devis vide.
    if ((mode === 'industriel' || mode === 'commercial') && panels <= 0) {
      throw {
        detail: 'Devis auto impossible : renseignez sur le lead une facture '
          + "d'électricité exploitable, la consommation mensuelle (kWh) ou la "
          + 'taille souhaitée en kWc, puis réessayez.',
      }
    }

    rows = autoFillLines(produits, {
      kwp: kwpAuto, panelW: PANEL_W_DEFAUT, nbPanneaux: panels,
      // QX19 — respecte la préférence de structure du lead (défaut acier).
      structureType: structFromLead(lead),
      // STKCAT10 — le PRODUIT épinglé prime dessus quand il existe.
      structureProduitId: structProduitFromLead(lead),
      marques,
      // PVORD — ordre par défaut de la société (voir la doc du paramètre
      // plus haut) ; absent/vide = ordre canonique inchangé.
      ordreLignes,
    })
    // PVMRQ — GARDE : une marque épinglée sans AUCUN candidat en stock laisse
    // des lignes PLACEHOLDER (aucun produit, 0 MAD) que le filtre
    // d'enregistrement plus bas (`r.produit && quantite > 0`) écarte
    // silencieusement — le devis partait SANS panneaux, à un prix effondré.
    // On refuse, avec EXACTEMENT le message du bandeau de DevisGenerator
    // (LeadDevisPanel rend `err.detail` tel quel).
    const marquesAbsentes = rows.marquesManquantes ?? []
    const panneauxSansProduit = rows.some(
      r => !r.produit && /panneau/i.test(r.designation || '')
        && parseFloat(r.quantite) > 0)
    if (marquesAbsentes.length) {
      throw {
        detail: `Marque épinglée introuvable au stock : ${marquesAbsentes
          .map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')}. `
          + 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.',
      }
    }
    if (panneauxSansProduit) {
      throw {
        detail: 'Devis auto impossible : aucun panneau du stock ne correspond '
          + 'à cette composition. Complétez le catalogue, puis réessayez.',
      }
    }
    // QX19 — scénario batterie SEMÉ depuis batterie_souhaitee du lead : porté
    // dans etude_params pour que le PDF (builder QF6) restreigne le document au
    // choix du client (« sans »/« avec »/« les deux »). Défaut « les deux »
    // (comportement historique) quand non renseigné.
    const _bat = lead.batterie_souhaitee
    extra.etude_params = {
      ...(extra.etude_params || {}),
      scenario: BATTERIE_LEAD_VERS_SCENARIO[_bat] ?? SCENARIO_LES_DEUX,
    }
    // U3 — le bloc PACT10/QF-REAL (12 factures RÉELLES du client semées dans
    // `etude_params`) vivait ICI ; il a MIGRÉ dans la branche résidentielle
    // ci-dessus, qui part au serveur. Il n'est plus atteignable d'ici : à ce
    // point, `mode` ne peut plus valoir 'residentiel'.

    // QX52 — industriel ET commercial partagent l'étude d'autoconsommation ; le
    // day-share diffère (industriel 80 % vs commercial 80 % archétype par défaut)
    // et chaque mode garde SON `mode_installation` (jamais un repli croisé).
    if (mode === 'industriel' || mode === 'commercial') {
      const ete = (lead.ete_differente && lead.facture_ete)
        ? parseFloat(lead.facture_ete) : hiver
      const moisAuto = hiver > 0 ? estimerMois(hiver, ete) : []
      // QJR665 (décision fondateur 01/10) — sans kWh saisis, l'étude prend la
      // consommation du BALAYAGE qui a choisi le kWc (`parametresBalayageCI`,
      // barème national COUV-HOR), jamais moyenne des factures ÷ kwhPrice :
      // taux, économies et payback décrivent le client dimensionné.
      // QJR603 — un lead « kWh seulement » porte peut-être `bill_kwh` seul :
      // il alimente l'étude en dernier recours (jamais devant la facture).
      const conso = (parseFloat(lead.conso_mensuelle_kwh) || 0)
        || consoMensuelleEtudeCI({
          factures: moisAuto, mode, distributeurDeclare: lead.distributeur,
        })
        || kwhMensuelsLeadPro(lead)
      extra.mode_installation = mode
      const _dayUsage = mode === 'commercial'
        ? DAY_USAGE_DEFAULTS['Commerciale'] : DAY_USAGE_DEFAULTS['Industrielle']
      const _scenarioPrev = extra.etude_params?.scenario
      const _etudeInd = (kwpAuto > 0 && conso > 0)
        ? computeEtudeIndustrielle({
            kwp: kwpAuto, consoMensuelleKwh: conso,
            dayUsagePct: _dayUsage,
            totalTtc: optionTotalsTTC(roundTripRowsTtc(rows), discountStr || '0').totalSans,
            kwhPrice, efficiency,
          })
        : null
      // QX19 — préserve le scénario batterie semé du lead (défaut industriel :
      // sans batterie, réseau) même quand l'étude industrielle est calculée.
      // QJR543 — l'étude BRUTE (kwc, prix_kwc, economies_annuelles… hors
      // schéma) passe par LA projection du générateur (QJR542) ; le scénario
      // part AVEC la création : sans lui, réseau + hybride + batterie
      // totaliseraient la somme des deux paniers.
      extra.etude_params = projeterEtudeMarche(mode, {
        etude: _etudeInd,
        choix: { scenario: lead.batterie_souhaitee ? _scenarioPrev : SCENARIO_SANS },
        entrees: (consoConnue) => (consoConnue != null ? { conso_annuelle: consoConnue } : {}),
        partDiurne: _dayUsage,
      })
      // Surface les chiffres clés (taux d'autoconsommation, économies, payback)
      // AVANT enregistrement, pour que l'appelant puisse les afficher.
      if (typeof onEtude === 'function') {
        onEtude({
          taux_autoconso: _etudeInd?.taux_autoconso,
          economies_annuelles: _etudeInd?.economies_annuelles,
          payback: _etudeInd?.payback,
        })
      }
    }
  }
  // QJR543 — UN appel atomique : devis + lignes + étude + scénario en un
  // seul commit serveur. Un échec ne laisse RIEN (plus de brouillon partiel
  // que « Ouvrir l'édition complète » doublait d'un second devis), et
  // `etude_params` est écrit par la transaction de /atomic (en POST /devis/
  // il était en lecture seule et ignoré : m3_jour, taux_autoconso, payback
  // et le scénario n'atteignaient jamais le devis).
  // PVORD (fondateur 19/08/2026) — ordre PAR DÉFAUT des lignes = l'ordre
  // canonique du simulateur (celui produit par `rows`, éventuellement déjà
  // réordonné selon `ParametresGammes.ordre_lignes`) : `ordre: idx` explicite.
  const lignes = rows
    .filter(r => r.produit && parseFloat(r.quantite) > 0)
    .map((r, idx) => ({
      produit: parseInt(r.produit),
      designation: r.designation,
      quantite: String(r.quantite),
      prix_unitaire: htFromTtc(r.prix_unit_ttc, r.taux_tva ?? 20),
      remise: '0',
      taux_tva: String(r.taux_tva ?? 20),
      ordre: idx,
    }))
  const { data } = await ventesApi.createDevisAtomic({
    lead: lead.id,
    statut: 'brouillon',
    taux_tva: '20.00',
    remise_globale: discountStr || '0',
    note: null,
    ...extra,
    lignes,
  })
  return data.id
}
