/* Création du « devis automatique » — logique PARTAGÉE entre le générateur
   complet (DevisGenerator) et le panneau devis inline de la fiche lead
   (LeadDevisPanel). Source unique : on ne duplique JAMAIS le calcul de prix.

   CIQ127 — les QUATRE marchés partent au SERVEUR (`POST /ventes/devis/auto/`) :
   résidentiel (moteur horaire, U3), agricole (pompage, AGR124) et
   commercial / industriel (moteur C&I, CIQ120). Cet écran ne dimensionne,
   ne compose et n'étudie plus rien : plus de balayage C&I par paliers, plus
   d'étude locale, plus de `createDevisAtomic`. Lit le lead directement (pas d'état React). */
import ventesApi from '../../api/ventesApi'
import { formatKwc, formatMAD, formatNumber } from '../../lib/format'
import fieldLabels, { CHOIX_BATTERIE_SOUHAITEE, LIBELLES_SECTIONS } from '../crm/workspace/fieldLabels'

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

// T4-X1-011 — un 500 (ou aucune réponse : réseau, délai) n'est PAS la faute de
// la fiche du lead : la seconde tentative, fiche inchangée, créait le devis.
// Un refus qui répond 4xx garde son message (et son champ nommé) ; une panne
// serveur le dit, et marque `serveur: true` pour que l'écran offre « Réessayer »
// (la route est idempotente 120 s : un nouvel essai ne crée jamais deux devis).
export const MESSAGE_SERVEUR_SANS_REPONSE = 'Le serveur n’a pas répondu (ou a rencontré une erreur) — '
  + 'la fiche du lead n’est pas en cause. Réessayez dans un instant.'
export const estPanneServeur = (err) => !err?.response || err.response.status >= 500

// AGR126 / CIQ127 — l'agricole et le C&I partent au serveur (AGR124, CIQ120) :
// un seul appel `POST /ventes/devis/auto/`, jamais `createDevisAtomic`. Le 422
// du serveur (donnée manquante, relevé du point d'eau, aucune taille ni
// composition chiffrable…) remonte TEL QUEL dans `err.detail` (+ `field`
// nommé) ; ses `alertes` vont à `onAlertes` (internes comprises : l'écran les
// marque « vendeur seulement »). Une cible kWc saisie POUR CE devis (EZ5)
// part en `target_kwc`, souveraine (D-QJR5-13), sans toucher le lead.
async function creerDevisServeur({ lead, discountStr, onAlertes, onResultat, targetKwc, marche, idempotencyKey }) {
  const cible = parseFloat(targetKwc)
  let creation
  try {
    creation = await ventesApi.creerDevisAuto({
      lead: lead.id,
      remise_globale: discountStr || '0',
      // AGNR39 — jamais pour le pompage : le champ découle de la pompe.
      ...(cible > 0 && marche !== 'agricole' ? { target_kwc: cible } : {}),
    // AGQ22 — agricole : l'écran (panneau lead, générateur) affiche lui-même
    // le refus nommé ; le toast global ferait un second message. AGQ23 — la
    // clé d'idempotence du panneau (agricole seulement : C&I inchangé).
    // ACAL1325 — C&I aussi : la création peut durer ~50 s, l'écran dit seul le
    // résultat (créé ou refusé), jamais un toast d'expiration en plus.
    }, { suppressErrorToast: true, ...(marche === 'agricole' && idempotencyKey ? { idempotencyKey } : {}) })
  } catch (err) {
    // AGQ23 (C-AGQ-022) — délai dépassé : le serveur a pu finir la création.
    if (err?.code === 'ECONNABORTED') {
      throw {
        detail: 'Le devis a peut-être été créé : la liste se rafraîchit.',
        delaiDepasse: true,
      }
    }
    if (estPanneServeur(err)) throw { detail: MESSAGE_SERVEUR_SANS_REPONSE, serveur: true }
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
  // ALEA51 — le retour du serveur (réf., kWc, total TTC, économie, retour,
  // postes à chiffrer) pour la bannière de succès : lu tel quel, rien calculé ici.
  if (typeof onResultat === 'function') onResultat(creation.data)
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
 * @param {function} onResultat   ALEA51 — rappel facultatif recevant la réponse du
 *                                serveur ({reference, kwc, total_ttc,
 *                                economie_an_1_ht, retour_ans,
 *                                postes_apres_visite…}) pour la bannière de succès
 * @param {string|number} targetKwc  EZ5 — puissance cible (kWc) demandée POUR
 *                                CE devis-là, sans toucher la fiche du lead.
 *                                Vide/absent = la taille souhaitée du lead,
 *                                sinon le moteur serveur dimensionne.
 * Les autres paramètres historiques (produits, quoteLogic, onEtude, marques,
 * ordreLignes, dispatch) sont acceptés et IGNORÉS : le serveur lit le
 * catalogue, les marques épinglées et l'ordre des lignes de la société.
 */
/**
 * T4-X1-004 — la taille tapée (3 kWc) et la taille composée par le serveur (3,55 kWc) diffèrent : l'écart est DIT, à partir
 * des seules valeurs SERVIES (le `kwc` et le `nb_panneaux` du devis ou de chacune de ses options) ; rien n'est recalculé.
 * UNE CAUSE N'EST DITE QUE SI LES DONNÉES SERVIES LA PROUVENT : « panneau entier » seulement quand, pour CHAQUE option qui
 * diffère, la taille servie est ≥ la demande ET l'écart est strictement inférieur à la puissance d'UN panneau de cette option
 * (kwc servi ÷ nombre de panneaux servi). Sinon (plusieurs panneaux d'écart, taille servie sous la demande, nombre de
 * panneaux non servi) : les deux chiffres seuls, sans cause. `null` quand rien ne diffère (ou qu'une valeur manque).
 */
export function alerteTailleArrondie(cibleKwc, donnees) {
  const cible = Number(cibleKwc)
  if (!(cible > 0) || !donnees) return null
  const options = Array.isArray(donnees.options) ? donnees.options.filter((o) => o?.variante && Number(o.kwc) > 0) : []
  const unique = Array.isArray(donnees.options) && donnees.options.length === 1 ? donnees.options[0] : null
  const servis = options.length
    ? options.map((o) => ({ nom: o.libelle || (o.variante === 'avec' ? 'Avec batterie' : 'Sans batterie'), kwc: Number(o.kwc), nb: Number(o.nb_panneaux) }))
    : (Number(donnees.kwc) > 0 ? [{
      nom: '',
      kwc: Number(donnees.kwc),
      // Le nombre de panneaux du devis : servi au devis, ou par son option unique de MÊME puissance.
      nb: Number(donnees.nb_panneaux ?? (unique && Number(unique.kwc) === Number(donnees.kwc) ? unique.nb_panneaux : NaN)),
    }] : [])
  const ecarts = servis.filter((o) => Math.abs(o.kwc - cible) > 0.005)
  if (!ecarts.length) return null
  const unPanneauAuDessus = (o) => Number.isInteger(o.nb) && o.nb > 0 && o.kwc >= cible && (o.kwc - cible) < o.kwc / o.nb
  if (ecarts.every(unPanneauAuDessus)) {
    const reel = ecarts.map((o) => `${o.nom ? `${o.nom} : ` : ''}${formatKwc(o.kwc)}`).join(' · ')
    return {
      code: 'taille_arrondie',
      message: `Vous avez demandé ${formatKwc(cible)} ; le devis est à ${reel} : le nombre de panneaux est entier, `
        + 'la taille composée est celle du panneau entier juste au-dessus de la demande.',
    }
  }
  const composee = ecarts.map((o) => `${formatKwc(o.kwc)}${o.nom ? ` (${o.nom})` : ''}`).join(' · ')
  return { code: 'taille_arrondie', message: `Taille demandée : ${formatKwc(cible)} ; taille composée : ${composee}.` }
}

export async function createAutoQuote({ lead, discountStr, onAlertes, onResultat, targetKwc, idempotencyKey }) {
  const mode = LEAD_TYPE_TO_MODE[lead.type_installation] || 'residentiel'
  // ── U3 (fondateur 20/08/2026) — LE RÉSIDENTIEL NE COMPOSE PLUS ICI ─────
  // Ordre fondateur APPLIQUÉ par ce fichier : la composition n'a plus
  // qu'UNE source de vérité (le serveur) et cet écran la consomme.
  //
  // Il y en avait bien deux : cet écran composait le kit en JavaScript
  // (`autoFillLines`, supprimé par ADEV69) pendant que le serveur le composait en Python
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
    // T4-X1-004 — la taille tapée part TELLE QUELLE : l'arrondir ici au
    // panneau de 710 W supposé (3 → 5 × 710 W = 3,55) faisait annoncer
    // « Taille imposée : 3,55 kWc » pour 3 tapés ; le serveur, qui connaît ses
    // vrais panneaux, en dérive lui-même le nombre de panneaux.
    const kwpAuto = tailleKwc > 0 ? tailleKwc : 0

    const etudeExtra = {}
    // AGNR34 (D-AGNR-1 option (a)) — plus de série de douze mois ni de conso
    // calculée au barème JS : le serveur lit les deux factures du lead
    // (`lead_bills_for_devis`) et dérive lui-même les marches (source
    // `facture_hiver_ete`). Seul le distributeur DÉCLARÉ du lead voyage. Le
    // `scenario`, lui, est décidé au serveur depuis `lead.batterie_souhaitee` (U2).
    if (hiver > 0) {
      const distributeurLead = ['onee', 'lydec', 'redal'].includes(lead.distributeur)
        ? lead.distributeur : undefined
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
      }, { suppressErrorToast: true }) // ACAL1325 — l'écran dit seul le résultat
    } catch (err) {
      // Le serveur parle FRANÇAIS (422 : marque épinglée introuvable,
      // données de dimensionnement manquantes…) et ses appelants lisent
      // `err.detail` — on rend son message tel quel, jamais un nôtre.
      // ALEA48 — le 409 nomme aussi le champ à compléter (`field`) : on le
      // relaie, comme la branche C&I, pour que l'écran propose « Compléter ».
      if (estPanneServeur(err)) throw { detail: MESSAGE_SERVEUR_SANS_REPONSE, serveur: true }
      const champ = err?.response?.data?.field
      throw {
        detail: err?.response?.data?.detail
          || "Le devis automatique a échoué — vérifiez la fiche du lead et réessayez.",
        ...(champ ? { field: champ } : {}),
      }
    }
    const id = reponse?.data?.id
    if (!id) {
      throw { detail: 'Devis créé sans identifiant — ouvrez-le depuis la liste des devis.' }
    }
    // ADEV123 — les suppositions du calcul résidentiel (présence, été = hiver,
    // kWh tirés des dirhams, 30° plein sud) partent à l'écran comme celles du C&I.
    if (typeof onAlertes === 'function') {
      const alertes = Array.isArray(reponse.data.alertes) ? reponse.data.alertes : []
      const arrondie = alerteTailleArrondie(cibleKwc, reponse.data) // T4-X1-004 — seule une taille TAPÉE pour ce devis
      onAlertes(arrondie ? [...alertes, arrondie] : alertes)
    }
    if (typeof onResultat === 'function') onResultat(reponse.data)
    return id
  }
  // CIQ127 — agricole (AGR126) et commercial / industriel : le serveur
  // étudie, dimensionne, compose et crée le brouillon ; rien n'est calculé ici.
  return creerDevisServeur({ lead, discountStr, onAlertes, onResultat, targetKwc, marche: mode, idempotencyKey })
}

/**
 * T4-X4-014 — LA phrase d'UNE option d'un devis à deux options : « Sans batterie :
 * 2,2 kWc · 37 800 MAD TTC ». Partagée par le bandeau « Devis créé » du devis
 * automatique et le panneau « Devis enregistré » du générateur. Une puissance non
 * fournie (`kwc` absent) est omise ; fournie mais illisible, elle s'écrit « — ».
 */
export function libelleOptionDevis(o) {
  const morceaux = []
  if (o.kwc !== undefined) {
    const k = Number(o.kwc)
    morceaux.push(Number.isFinite(k) && k > 0 ? formatKwc(k) : '—')
  }
  const t = Number(o.total_ttc)
  if (o.total_ttc != null && Number.isFinite(t)) morceaux.push(`${formatMAD(t, { decimals: 0 })} TTC`)
  return `${o.libelle} : ${morceaux.join(' · ')}`
}

/**
 * T4-X4-014 — les deux options d'un devis qu'on vient d'enregistrer, lues sur ce que
 * le serveur sert déjà avec le devis (`comparaison_options`, totaux ×N compris) :
 * `[]` pour un devis à une seule option (rien à nommer).
 */
export function optionsDepuisComparaison(devisData) {
  const c = devisData?.comparaison_options
  if (!c || devisData.nb_options !== 2 || c.sans?.ttc == null || c.avec?.ttc == null) return []
  return [
    { variante: 'sans', libelle: 'Sans batterie', total_ttc: c.sans.ttc },
    { variante: 'avec', libelle: 'Avec batterie', total_ttc: c.avec.ttc },
  ]
}

/**
 * T4-X6-008 — le titre des `alertes` de l'ENREGISTREMENT d'une édition
 * (réponse de replace-lines : chaque quantité que le serveur a réécrite ou
 * gardée) : « 2 ajustements à l'enregistrement : ». Aucun ajustement : null.
 */
export function titreAjustementsEnregistrement(alertes) {
  const n = Array.isArray(alertes) ? alertes.length : 0
  if (!n) return null
  return `${n} ajustement${n > 1 ? 's' : ''} à l’enregistrement :`
}

/**
 * ALEA51 — la phrase du bandeau de SUCCÈS après un devis automatique :
 * « DEV-… · 65 kWc · 212 100 MAD TTC · économie ≈ 102 000 MAD/an · retour ≈
 * 4,2 ans · 3 postes à chiffrer après la visite ». Chaque morceau vient de la
 * réponse du serveur ; un morceau absent (null) est OMIS — jamais un chiffre
 * inventé (retour null = investissement incomplet).
 */
export function libelleSuccesDevisAuto(resultat) {
  if (!resultat) return ''
  const morceaux = []
  const avecBatterie = Number(resultat.economie_an_1_ht_avec)
  const optionAvec = resultat.economie_an_1_ht_avec != null && Number.isFinite(avecBatterie) && avecBatterie > 0
  if (resultat.reference) morceaux.push(resultat.reference)
  // T4-V2-013 — deux options servies (`options`) : chacune avec SON kWc et SON
  // total ; `kwc`/`total_ttc` de tête sont ceux de l'option affichée (avec).
  const options = Array.isArray(resultat.options) ? resultat.options.filter((o) => o?.variante) : []
  if (options.length === 2) {
    for (const o of options) morceaux.push(libelleOptionDevis(o))
  } else {
    const kwc = Number(resultat.kwc)
    // T4-U1-026 — la puissance du devis, jamais arrondie à l'entier.
    if (Number.isFinite(kwc) && kwc > 0) morceaux.push(formatKwc(kwc))
    const ttc = Number(resultat.total_ttc)
    if (resultat.total_ttc != null && Number.isFinite(ttc)) {
      morceaux.push(`${formatMAD(ttc, { decimals: 0 })} TTC`)
    }
  }
  // T4-V2-015 — une SEULE option : laquelle, et la raison quand c'est la fiche.
  const unique = resultat.option_unique
  if (unique && typeof unique === 'object') {
    morceaux.push(`option unique : ${unique.batterie ? 'avec' : 'sans'} batterie`
      + (unique.souhait_fiche ? (unique.batterie ? ' (batterie souhaitée sur la fiche)' : ' (sans batterie souhaité sur la fiche)') : ''))
    // Relecture m2 — où demander la comparaison : seulement quand c'est la fiche qui a décidé
    // (la changer donne alors les deux options) ; libellés lus sur la fiche, jamais recopiés.
    if (unique.souhait_fiche) {
      morceaux.push(`pour comparer les deux, choisissez « ${CHOIX_BATTERIE_SOUHAITEE.les_deux} » au champ`
        + ` « ${fieldLabels.batterie_souhaitee.label} » de la fiche (${LIBELLES_SECTIONS.toiture})`)
    }
  }
  const eco = Number(resultat.economie_an_1_ht)
  if (resultat.economie_an_1_ht != null && Number.isFinite(eco) && eco > 0) {
    morceaux.push(`${optionAvec ? 'sans batterie : ' : ''}économie ≈ ${formatMAD(Math.round(eco / 100) * 100, { decimals: 0 })}/an`)
  }
  const retour = Number(resultat.retour_ans)
  if (resultat.retour_ans != null && Number.isFinite(retour) && retour > 0) {
    morceaux.push(`retour ≈ ${formatNumber(retour, { decimals: 1 })} ans`)
  }
  if (optionAvec) {
    let avec = `avec batterie : économie ≈ ${formatMAD(Math.round(avecBatterie / 100) * 100, { decimals: 0 })}/an`
    const retourAvec = Number(resultat.retour_ans_avec)
    if (resultat.retour_ans_avec != null && Number.isFinite(retourAvec) && retourAvec > 0) {
      avec += ` · retour ≈ ${formatNumber(retourAvec, { decimals: 1 })} ans`
    }
    morceaux.push(avec)
  }
  const postes = Array.isArray(resultat.postes_apres_visite) ? resultat.postes_apres_visite.length : 0
  if (postes > 0) {
    morceaux.push(`${postes} poste${postes > 1 ? 's' : ''} à chiffrer après la visite`)
  }
  return morceaux.join(' · ')
}
