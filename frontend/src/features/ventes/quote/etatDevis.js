// QJR658 — L'ÉDITION COMPLÈTE EN UN MODULE PUR : devis ⇄ état d'écran.
//
// `devisVersEtat(devis)` lit un devis servi (GET /ventes/devis/<id>/) et rend
// l'état que l'écran pose à la réouverture (`?edit=`) ; `etatVersEcritures`
// rend ce que l'enregistrement écrit (replace-lines : `{ lignes, entete }`,
// et le bloc `etude` de la fusion `etude_params`). Le générateur n'a plus de
// mappeur écrit à la main : il appelle `devisVersEtat` puis pose l'état, et
// construit ses écritures par `etatVersEcritures`. L'aller-retour est EXÉCUTÉ
// par `etatDevis.test.mjs` sur un devis par marché (plus de regex sur la
// source).
//
// Il COMPOSE les modules existants sans les réécrire : `lignesEcran.js`
// (QJR523, lignes serveur ⇄ écran), `reouverture.js` (QJR526, wattage /
// structure / hors-réseau relus des lignes), `etudeMarcheBloc.js` (QJR542,
// projection des clés `etude_params`) et `echeancierEdition.js` (QJR624).
//
// Convention : une clé ABSENTE (`undefined`) de l'état veut dire « le devis ne
// la porte pas, l'écran garde sa valeur » — jamais une valeur inventée.
// Fonctions PURES : aucun React, aucun réseau (node --test).
import {
  COMMERCIAL_CATEGORY_QUESTIONS,
  consoAnnuelleDepuisFactures, consoDescendDesFactures,
} from '../solar.js'
import { SCENARIO_SANS, SCENARIO_AVEC } from './sizingReducer.js'
import { lignesServeurVersEcran, lignesEcranVersPayload } from './lignesEcran.js'
import { deriverReouverture } from './reouverture.js'
import {
  projeterEtudeMarche, ecoDepuisSaisies, saisiesEconomiePompage,
} from './etudeMarcheBloc.js'
import { echeancierVersSaisie, saisieVersEcheancier } from '../echeancierEdition.js'

//: Les options recommandées qu'un devis peut avoir FIGÉES (QJR524).
const RECOS = ['Aucune recommandation', SCENARIO_SANS, SCENARIO_AVEC]

const present = (v) => v !== undefined && v !== null && v !== ''
const texte = (v) => (present(v) ? String(v) : undefined)

/** Le devis servi → l'état de l'écran d'Édition complète. */
export function devisVersEtat(d) {
  const devis = d || {}
  const e = devis.etude_params || {}
  const mode = devis.mode_installation || undefined
  const lignes = lignesServeurVersEcran(devis.lignes ?? [], devis.taux_tva)

  const etat = {
    mode,
    leadId: devis.lead ? String(devis.lead) : undefined,
    clientId: !devis.lead && devis.client ? String(devis.client) : undefined,
    discountPct: String(parseFloat(devis.remise_globale) || 0),
    tauxTva: String(devis.taux_tva ?? '20.00'),
    dateValidite: devis.date_validite || undefined,
    note: devis.note || undefined,
    // QJR527 — le prix cible DU DEVIS gagne, vide compris.
    prixCible: devis.prix_cible_kwc != null ? String(parseFloat(devis.prix_cible_kwc)) : '',
    // QJR624 — l'échéancier du devis (`null` = celui de la société).
    echeancier: echeancierVersSaisie(devis.echeancier),
    lignes,
    // L-2OPT — panneaux de la branche SANS (commun + 'sans').
    panneaux: lignes
      .filter(r => /panneau/i.test(r.designation) && r.variante !== 'avec')
      .reduce((s, r) => s + (parseFloat(r.quantite) || 0), 0),
    // QJR526 — wattage, structure, hors-réseau, composition libre.
    reouverture: deriverReouverture(lignes, { mode }),
    scenario: e.scenario || undefined,
    leadValeursModifiees: Array.isArray(devis.lead_valeurs_modifiees)
      ? devis.lead_valeurs_modifiees : [],
  }
  etat.echeancierAEnvoyer = etat.echeancier != null

  // PVMRQ — gamme du devis.
  if (e.gamme && typeof e.gamme === 'object' && e.gamme.nom) etat.gammeNom = String(e.gamme.nom)

  // QJR524 — l'option recommandée ENREGISTRÉE (repli : clé legacy).
  const reco = [e.recommended_option, e.recommended_choice].find(v => RECOS.includes(v))
  if (reco) etat.recommendedChoice = reco
  else if (e.recommended_choice === 'Auto') etat.recommendedChoice = 'Auto'

  // QJ31 — ×N villas identiques.
  const n = parseInt(e.nombre_proprietes, 10)
  if (Number.isFinite(n) && n > 1) {
    etat.multiMode = 'multiplier'
    etat.nombreProprietes = String(n)
  }
  // QJR530 — mode « villas » : groupes relus des lignes.
  if (lignes.some(r => r.groupeIndex != null)) {
    const groupes = new Map([[0, 'Équipement commun']])
    for (const r of lignes) {
      const idx = Number(r.groupeIndex)
      if (r.groupeIndex == null || !Number.isFinite(idx) || groupes.has(idx)) continue
      groupes.set(idx, r.groupeLabel || `Villa ${idx}`)
    }
    etat.villaGroups = [...groupes.entries()]
      .sort((a, b) => a[0] - b[0]).map(([index, label]) => ({ index, label }))
    etat.multiMode = 'villas'
  }

  // QX50 / QXMT / QJR528 — étude réseau.
  if (e.injection_82_21 || e.injection_dh_an != null) etat.injectionEnabled = true
  if (e.tension_raccordement === 'mt') etat.tension = 'mt'
  if (mode === 'industriel' && e.part_diurne_pct != null
      && Number.isFinite(Number(e.part_diurne_pct))) {
    etat.partDiurne = String(Number(e.part_diurne_pct))
  }
  if (e.repartition_mt && typeof e.repartition_mt === 'object') {
    const r = e.repartition_mt
    etat.repartitionMt = {
      pointe: r.pointe != null ? String(r.pointe) : '',
      pleines: r.pleines != null ? String(r.pleines) : '',
      creuses: r.creuses != null ? String(r.creuses) : '',
    }
  }
  // QX44 — étude commerciale : catégorie + réponses.
  if (e.categorie_commerciale) {
    etat.categorieCommerciale = String(e.categorie_commerciale)
    const reponses = {}
    for (const q of COMMERCIAL_CATEGORY_QUESTIONS[etat.categorieCommerciale] || []) {
      if (e[q.key] !== undefined && e[q.key] !== null) reponses[q.key] = e[q.key]
    }
    etat.commercialAnswers = reponses
  }

  // Pompage (agricole).
  etat.pompe = {
    cv: e.pompe_cv ? String(e.pompe_cv) : undefined,
    kw: present(e.pompe_kw) ? Number(e.pompe_kw) : undefined,
    hmt: e.hmt_m ? String(e.hmt_m) : undefined,
    debit: e.debit_souhaite_m3h ? String(e.debit_souhaite_m3h) : undefined,
    heures: e.heures_pompage ? String(e.heures_pompage) : undefined,
    type: texte(e.type_pompe),
    alim: texte(e.alim),
    profondeur: texte(e.profondeur_m),
    distance: texte(e.distance_m),
  }
  if (e.conso_annuelle) etat.consoMensuelle = String(Math.round(e.conso_annuelle / 12))

  // QF4 — distributeur + conso annuelle réelle.
  if (e.distributeur) {
    etat.distributeur = String(e.distributeur)
    etat.distributeurChoisi = true
  }
  const factures = Array.isArray(e.factures_mensuelles_reelles)
    && e.factures_mensuelles_reelles.length === 12
    ? e.factures_mensuelles_reelles : null
  if (factures) etat.monthly = factures.map(v => Number(v) || 0)
  etat.consoStockee = e.conso_annuelle > 0 ? {
    valeur: Number(e.conso_annuelle),
    factures,
    descendDesFactures: consoDescendDesFactures(e.conso_annuelle, factures, e.distributeur),
  } : null
  if (etat.consoStockee && !etat.consoStockee.descendDesFactures) {
    etat.realBillMode = 'kwh'
    etat.realBillKwh = String(Math.round(e.conso_annuelle / 12))
  }

  // Exploitation guidée (toutes optionnelles). AGR212 — l'énergie et la
  // dépense DÉCLARÉES se relisent dans `saisies_economie_pompage` (plus
  // jamais `current_fuel` / `fuel_spend_current`).
  etat.farm = {
    region: texte(e.region),
    crop: texte(e.crop),
    surfaceHa: texte(e.surface_ha),
    irrigation: texte(e.irrigation_method),
    hmtStatic: texte(e.hmt_static),
    hmtDrawdown: texte(e.hmt_drawdown),
  }
  etat.saisiesEco = ecoDepuisSaisies(e.saisies_economie_pompage)
  return etat
}

/** Les CHOIX du commercial (QF7) — `nombre_proprietes` part à `null` hors ×N
 *  (règle Z2 : la clé est retirée). */
export function choixDeEtat(etat, { recommended } = {}) {
  const choix = {}
  if (etat.scenario) choix.scenario = etat.scenario
  const reco = recommended ?? (RECOS.includes(etat.recommendedChoice) ? etat.recommendedChoice : null)
  if (reco) choix.recommended_option = reco
  const n = etat.multiMode === 'multiplier' ? parseInt(etat.nombreProprietes, 10) : 1
  choix.nombre_proprietes = (Number.isFinite(n) && n > 1) ? n : null
  return choix
}

/** Les ENTRÉES réelles relues du devis (factures, conso, distributeur) : la
 *  conso saisie repart telle quelle ; une conso qui descend des factures est
 *  re-dérivée au barème (COUV-HOR). */
export function entreesDeEtat(etat) {
  const entrees = {}
  const stockee = etat.consoStockee
  const factures = Array.isArray(etat.monthly) ? etat.monthly : (stockee?.factures || null)
  if (factures) entrees.factures_mensuelles_reelles = factures.map(v => parseFloat(v) || 0)
  let conso = null
  let auBareme = false
  if (stockee && !stockee.descendDesFactures) conso = stockee.valeur
  if (conso == null && factures) {
    const derivee = consoAnnuelleDepuisFactures(factures, etat.distributeur || 'onee')
    if (derivee > 0) { conso = derivee; auBareme = true }
  }
  if (conso != null) {
    entrees.conso_annuelle = conso
    if (auBareme || etat.distributeurChoisi) entrees.distributeur = etat.distributeur || 'onee'
  } else if (etat.distributeur && etat.distributeur !== 'onee') {
    entrees.distributeur = etat.distributeur
  }
  return entrees
}

/**
 * L'état de l'écran → les écritures de l'enregistrement.
 *
 * @param {object} etat  état d'écran (celui de `devisVersEtat`, ou celui que
 *   l'écran assemble au moment d'enregistrer)
 * @param {object} [vif] valeurs CALCULÉES à l'écran que l'état ne porte pas :
 *   `etude` (étude I/C du moment), `pompage` (dimensionnement retenu),
 *   `entrees` (entrées réelles de la session), `recommended` (option
 *   effective). Absentes → dérivées de l'état seul.
 * @returns {{lignes: Array, entete: object, etude: object|null}}
 */
export function etatVersEcritures(etat, vif = {}) {
  const entete = {
    date_validite: etat.dateValidite || null,
    taux_tva: etat.tauxTva,
    remise_globale: etat.discountPct || '0',
    note: etat.note || null,
    mode_installation: etat.mode,
    prix_cible_kwc: etat.prixCible !== '' && etat.prixCible != null ? etat.prixCible : null,
  }
  // QJR624 — l'échéancier ne part que s'il était propre au devis ou touché.
  if (etat.echeancierAEnvoyer) entete.echeancier = saisieVersEcheancier(etat.echeancier)

  const pompe = etat.pompe || {}
  const farm = etat.farm || {}
  const etude = projeterEtudeMarche(etat.mode, {
    etude: vif.etude,
    choix: choixDeEtat(etat, { recommended: vif.recommended }),
    entrees: vif.entrees ?? entreesDeEtat(etat),
    partDiurne: etat.partDiurne,
    tensionRaccordement: etat.tension,
    repartitionMt: etat.repartitionMt,
    categorie: etat.categorieCommerciale,
    reponses: etat.commercialAnswers || {},
    pompage: vif.pompage ?? { pompe_cv: pompe.cv, pompe_kw: pompe.kw },
    saisiePompage: {
      hmt: pompe.hmt, debit: pompe.debit, heures: pompe.heures,
      typePompe: pompe.type, alim: pompe.alim,
      profondeur: pompe.profondeur, distance: pompe.distance,
    },
    exploitation: {
      irrigation: farm.irrigation, region: farm.region, crop: farm.crop,
      surfaceHa: farm.surfaceHa,
      hmtStatic: farm.hmtStatic, hmtDrawdown: farm.hmtDrawdown,
      saisiesEconomie: saisiesEconomiePompage(etat.saisiesEco),
    },
  })

  return {
    lignes: lignesEcranVersPayload(etat.lignes || [], { multiMode: etat.multiMode }),
    entete,
    etude,
  }
}
