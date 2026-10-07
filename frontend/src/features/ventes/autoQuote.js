/* Création du « devis automatique » — logique PARTAGÉE entre le générateur
   complet (DevisGenerator) et le panneau devis inline de la fiche lead
   (LeadDevisPanel). Source unique : on ne duplique JAMAIS le calcul de prix.

   CIQ127 — les QUATRE marchés partent au SERVEUR (`POST /ventes/devis/auto/`) :
   résidentiel (moteur horaire, U3), agricole (pompage, AGR124) et
   commercial / industriel (moteur C&I, CIQ120). Cet écran ne dimensionne,
   ne compose et n'étudie plus rien : plus de balayage C&I par paliers, plus
   d'étude locale, plus de `createDevisAtomic`. Lit le lead directement (pas d'état React). */
import ventesApi from '../../api/ventesApi'
import {
  estimerMois, panneauxPourKwc,
  // QJR576 — UNE conversion panneaux ↔ kWc et UN wattage par défaut.
  kwcPourPanneaux, PANEL_W_DEFAUT,
} from './solar'
import {
  // PACT10/QF-REAL — consommation annuelle RÉELLE du lead (résidentiel),
  // dérivée de ses factures par le barème national (COUV-HOR).
  consoAnnuelleDepuisFactures,
} from './calc/tarifs.js'

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

// AGR126 / CIQ127 — l'agricole et le C&I partent au serveur (AGR124, CIQ120) :
// un seul appel `POST /ventes/devis/auto/`, jamais `createDevisAtomic`. Le 422
// du serveur (donnée manquante, relevé du point d'eau, aucune taille ni
// composition chiffrable…) remonte TEL QUEL dans `err.detail` (+ `field`
// nommé) ; ses `alertes` vont à `onAlertes` (internes comprises : l'écran les
// marque « vendeur seulement »). Une cible kWc saisie POUR CE devis (EZ5)
// part en `target_kwc`, souveraine (D-QJR5-13), sans toucher le lead.
async function creerDevisServeur({ lead, discountStr, onAlertes, targetKwc, marche }) {
  const cible = parseFloat(targetKwc)
  let creation
  try {
    creation = await ventesApi.creerDevisAuto({
      lead: lead.id,
      remise_globale: discountStr || '0',
      ...(cible > 0 ? { target_kwc: cible } : {}),
    })
  } catch (err) {
    const data = err?.response?.data || {}
    throw {
      detail: data.detail
        || (marche === 'agricole'
          ? 'Le devis automatique agricole a échoué — vérifiez la fiche du lead et réessayez.'
          : 'Le devis automatique a échoué — vérifiez la fiche du lead et réessayez.'),
      ...(data.field ? { field: data.field } : {}),
    }
  }
  const id = creation?.data?.id
  if (!id) {
    throw { detail: 'Devis créé sans identifiant — ouvrez-le depuis la liste des devis.' }
  }
  if (typeof onAlertes === 'function') {
    onAlertes(Array.isArray(creation.data.alertes) ? creation.data.alertes : [])
  }
  return id
}

/**
 * Crée un devis automatique depuis un lead (au SERVEUR, quel que soit le
 * marché). Retourne l'id du devis créé. Lève { detail[, field] } avec le
 * message du serveur tel quel.
 *
 * @param {object}   lead         Lead complet (facture_hiver, taille souhaitée…)
 * @param {string}   discountStr  Remise globale en %
 * @param {function} onAlertes    rappel facultatif recevant les `alertes` du
 *                                devis créé par le serveur ([] sans alerte)
 * @param {string|number} targetKwc  EZ5 — puissance cible (kWc) demandée POUR
 *                                CE devis-là, sans toucher la fiche du lead.
 *                                Vide/absent = la taille souhaitée du lead,
 *                                sinon le moteur serveur dimensionne.
 * Les autres paramètres historiques (produits, quoteLogic, onEtude, marques,
 * ordreLignes, dispatch) sont acceptés et IGNORÉS : le serveur lit le
 * catalogue, les marques épinglées et l'ordre des lignes de la société.
 */
export async function createAutoQuote({ lead, discountStr, onAlertes, targetKwc }) {
  const mode = LEAD_TYPE_TO_MODE[lead.type_installation] || 'residentiel'
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
  // Ce qui reste À L'ÉCRAN est la taille EXPLICITE (si un humain l'a
  // choisie) et l'étude PACT10 : ce sont des décisions commerciales, pas une
  // composition — elles voyagent en paramètres, jamais en lignes.
  if (mode === 'residentiel') {
    const hiver = parseFloat(lead.facture_hiver) || 0
    // QX19 / EZ5 / QJR602 (D-QJR5-13) — une taille EXPLICITE (cible du devis ou
    // taille souhaitée du lead) est SOUVERAINE, telle quelle ; sans elle, le
    // moteur horaire serveur dimensionne (U3-MOTEUR, `target_kwc` omis).
    const cibleKwc = parseFloat(targetKwc) || 0
    const tailleKwc = cibleKwc > 0 ? cibleKwc : (parseFloat(lead.taille_souhaitee_kwc) || 0)
    const panels = tailleKwc > 0 ? panneauxPourKwc(tailleKwc, PANEL_W_DEFAUT) : 0
    const kwpAuto = panels > 0 ? kwcPourPanneaux(panels, PANEL_W_DEFAUT) : 0

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
  // CIQ127 — agricole (AGR126) et commercial / industriel : le serveur
  // étudie, dimensionne, compose et crée le brouillon ; rien n'est calculé ici.
  return creerDevisServeur({ lead, discountStr, onAlertes, targetKwc, marche: mode })
}
