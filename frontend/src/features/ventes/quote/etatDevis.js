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
  consoAnnuelleDepuisFactures, consoDescendDesFactures, comptePanneauxOption,
} from '../solar.js'
import { SCENARIO_SANS, SCENARIO_AVEC } from './sizingReducer.js'
import { lignesServeurVersEcran, lignesEcranVersPayload } from './lignesEcran.js'
import { deriverReouverture } from './reouverture.js'
import {
  projeterEtudeMarche, ecoDepuisSaisies, saisiesEconomiePompage,
  attestationDepuisEtude,
} from './etudeMarcheBloc.js'
import {
  POMPAGE_SAISIE_VIDE, etatPompageEcran,
} from '../etudePompagePreviewPur.js'
import {
  echeancierVersSaisie, saisieVersEcheancier, conditionsDepuisDevis, conditionsVersEntete,
} from '../echeancierEdition.js'
import { entreesCiV2, profilDepuisEtude } from './profilCi.js'
import { tarifDeclareDepuisSaisie, saisiesEconomieCi } from './etudeMarcheBloc.js'
import { saisieDepuisTarifDeclare, ecoCiDepuisSaisies } from './reouverture.js'

//: Les options recommandées qu'un devis peut avoir FIGÉES (QJR524).
const RECOS = ['Aucune recommandation', SCENARIO_SANS, SCENARIO_AVEC]

const present = (v) => v !== undefined && v !== null && v !== ''
// CIQ226 — une condition « vide » : null ou texte vide.
const estVide = (v) => v === null || v === undefined || v === ''
const texte = (v) => (present(v) ? String(v) : undefined)

// ── AGR130 — pompage : ENTRÉES v2 ⇄ états d'écran (`?edit=` et enregistrer) ──
// L'écran garde ses états historiques (CV, HMT, débit, profondeur, distance,
// niveaux, culture) ET les blocs de l'AGR128 (`pompageSaisie`) ; l'étude
// stockée n'a qu'UNE forme, celle du corps de l'aperçu. Ces deux fonctions
// sont l'aller et le retour de CETTE correspondance — exécutées par
// `etatDevis.test.mjs` (enregistrer → rouvrir → enregistrer = identique).
const sf = (v) => (present(v) ? String(v) : '')

/** `etude_params` (entrées v2) → { pompe, farm, saisie } de l'écran. */
export function pompageDepuisEtude(e) {
  const b = e.besoin || {}
  const s = e.source || {}
  const h = e.hmt_entrees || {}
  const c = h.conduite || null
  const cu = Array.isArray(b.cultures) ? (b.cultures[0] || {}) : {}
  const detail = [h.denivele_m, h.pertes_singulieres_m, h.pression_service_bar]
    .some(present) || Boolean(c)
  const compteur = s.compteur === true ? 'oui' : s.compteur === false ? 'non' : ''
  const saisie = {
    ...POMPAGE_SAISIE_VIDE,
    mode_pompe: e.mode_pompe || '',
    plaque: {
      kw: sf(e.plaque?.kw), tension_v: sf(e.plaque?.tension_v),
      phases: sf(e.plaque?.phases), courant_a: sf(e.plaque?.courant_a),
    },
    besoin: {
      mode: b.mode || '', volume_m3_jour: sf(b.volume_m3_jour),
      mois_pointe: sf(b.mois_pointe), debit_actuel_m3h: sf(b.debit_actuel_m3h),
      heures_actuelles_jour: sf(b.heures_actuelles_jour),
    },
    source: {
      debit_exploitation_m3h: sf(s.debit_exploitation_m3h),
      debit_exploitation_origine: sf(s.debit_exploitation_origine),
      debit_exploitation_date: sf(s.debit_exploitation_date),
      debit_autorise_m3h: sf(s.debit_autorise_m3h),
      volume_annuel_autorise_m3: sf(s.volume_annuel_autorise_m3),
      compteur, niveau_dynamique_m: sf(s.niveau_dynamique_m),
      diametre_tubage_mm: sf(s.diametre_tubage_mm),
      profondeur_calage_m: sf(s.profondeur_calage_m),
      volume_reservoir_m3: sf(s.volume_reservoir_m3),
    },
    hmt: {
      detail, denivele_m: sf(h.denivele_m),
      pertes_singulieres_m: sf(h.pertes_singulieres_m),
      pression_service_bar: sf(h.pression_service_bar),
      conduite: {
        materiau: sf(c?.materiau), diametre_interieur_mm: sf(c?.diametre_interieur_mm),
        longueur_m: sf(c?.longueur_m), c_hazen_williams: sf(c?.c_hazen_williams),
      },
    },
    options_cochees: Array.isArray(e.options_cochees) ? [...e.options_cochees] : [],
    taille: e.taille || '',
    localisation: e.localisation || null,
  }
  return {
    saisie,
    pompe: {
      cv: sf(e.plaque?.cv) || undefined,
      hmt: sf(h.saisie_m) || undefined,
      debit: sf(b.debit_souhaite_m3h) || undefined,
      type: texte(e.type_pompe),
      alim: texte(e.alim),
      profondeur: texte(s.profondeur_forage_m),
      distance: texte(e.distance_champ_m),
    },
    farm: {
      region: texte(b.region), crop: texte(cu.crop),
      surfaceHa: texte(cu.surface_ha), irrigation: texte(cu.irrigation),
      hmtStatic: texte(s.niveau_statique_m), hmtDrawdown: texte(s.rabattement_m),
    },
  }
}

/** L'état d'écran → l'état du corps de l'aperçu (celui que `entreesPompageV2` projette). */
export function entreesPompageEcran(etat) {
  const pompe = etat.pompe || {}
  const farm = etat.farm || {}
  const saisie = etat.pompageSaisie || POMPAGE_SAISIE_VIDE
  const corps = etatPompageEcran(saisie, {
    pompeCv: pompe.cv, pompeType: pompe.type, pompeAlim: pompe.alim,
    pompeHmt: pompe.hmt, pompeDebit: pompe.debit,
    pompeProfondeur: pompe.profondeur, pompeDistance: pompe.distance,
    farmRegion: farm.region, farmCrop: farm.crop, farmSurfaceHa: farm.surfaceHa,
    farmIrrigation: farm.irrigation, farmHmtStatic: farm.hmtStatic,
    farmHmtDrawdown: farm.hmtDrawdown,
  })
  // La localisation lue du devis (ville, lat, lon) ne se perd pas.
  if (saisie.localisation) corps.localisation = { ...saisie.localisation }
  return corps
}

/** Le devis servi → l'état de l'écran d'Édition complète. */
export function devisVersEtat(d, { bareme = null, produits = [] } = {}) {
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
    // AGNR45 — même règle que le kWc facturé (AGNR18) : `isPanel` sur la
    // désignation + le nom du produit lié (`produits`, catalogue de l'écran),
    // jamais `/panneau/i` (20 × « JA Solar 550 Wc » rouvraient à 0).
    panneaux: comptePanneauxOption(lignes, 'sans', produits),
    // QJR526 — wattage, structure, hors-réseau, composition libre.
    reouverture: deriverReouverture(lignes, { mode }),
    scenario: e.scenario || undefined,
    leadValeursModifiees: Array.isArray(devis.lead_valeurs_modifiees)
      ? devis.lead_valeurs_modifiees : [],
  }
  etat.echeancierAEnvoyer = etat.echeancier != null
  // CIQ226 — conditions contractuelles déclarées (retenue, pénalités, caution,
  // organisme financeur, référence de commande).
  etat.conditions = conditionsDepuisDevis(devis)
  // Les clés que le devis PORTE déjà : elles repartent même vidées (pour les
  // effacer) ; une clé jamais posée et toujours vide n'est pas envoyée.
  etat.conditionsServies = Object.keys(conditionsVersEntete(etat.conditions))
    .filter((k) => !estVide(conditionsVersEntete(etat.conditions)[k]))

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

  // CIQ125 — C&I : le profil déclaré se relit de ses ENTRÉES v2 (jamais
  // des dérivées `etude_ci`), la ville du site avec lui.
  if (mode === 'industriel' || mode === 'commercial') {
    etat.profilCi = profilDepuisEtude(e)
    etat.villeCi = e.site?.ville || null
    // CIQ222 — le tarif de la facture du client, tel que saisi.
    etat.tarifSaisie = saisieDepuisTarifDeclare(e.tarif_declare)
    // CIQ223 — les saisies de l'économie C&I, telles que saisies.
    etat.ecoCi = ecoCiDepuisSaisies(e.saisies_economie_ci)
  }
  // QX44 — étude commerciale : catégorie + réponses.
  if (e.categorie_commerciale) {
    etat.categorieCommerciale = String(e.categorie_commerciale)
    const reponses = {}
    // CIQ131 / CIQ129 — les réponses se relisent de l'entrée v2 du moteur
    // (`rythme.reponses_categorie`), heures données comprises (cuisson,
    // service, garde, dates de fermeture) ; plus jamais à plat (`e[q.key]`).
    const v2 = e.rythme?.reponses_categorie
    if (v2 && typeof v2 === 'object') {
      for (const [cle, valeur] of Object.entries(v2)) {
        if (valeur !== null && valeur !== undefined) reponses[cle] = valeur
      }
    }
    etat.commercialAnswers = reponses
  }

  // Pompage (agricole) — AGR130 : relu des ENTRÉES v2 (jamais des dérivées).
  const { pompe, farm: ferme, saisie } = pompageDepuisEtude(e)
  etat.pompe = pompe
  etat.pompageSaisie = saisie
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
    // AGNR35 — une conso dérivée au barème SOCIÉTÉ est reconnue aussi.
    descendDesFactures: consoDescendDesFactures(e.conso_annuelle, factures, e.distributeur, bareme),
    // AGNR35 — la conso stockée a-t-elle été dérivée au barème société ?
    // Sinon, ré-enregistrer sans toucher la re-dérive au barème qui l'a
    // produite : jamais un chiffre d'un devis existant changé en silence.
    auBaremeSociete: Boolean(bareme && factures && Math.abs(Number(e.conso_annuelle)
      - consoAnnuelleDepuisFactures(factures, null, bareme.tranches, bareme.chargesFixes)) <= 12),
  } : null
  if (etat.consoStockee && !etat.consoStockee.descendDesFactures) {
    etat.realBillMode = 'kwh'
    etat.realBillKwh = String(Math.round(e.conso_annuelle / 12))
  }

  // Exploitation guidée (toutes optionnelles). AGR212 — l'énergie et la
  // dépense DÉCLARÉES se relisent dans `saisies_economie_pompage` (plus
  // jamais `current_fuel` / `fuel_spend_current`).
  etat.farm = {
    ...ferme,
    // AGR218 — l'attestation d'usage agricole se relit telle que saisie.
    attestation: attestationDepuisEtude(e.attestation_usage_agricole),
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
/**
 * AGNR35 — le barème avec lequel RE-DÉRIVER la conso d'un devis : celui de la
 * société, SAUF quand la conso stockée descend de ces mêmes factures
 * (inchangées) au barème NATIONAL — elle est alors re-dérivée au national,
 * donc identique (aucun chiffre d'un devis existant ne bouge sans geste).
 */
export function baremePourDerivation(bareme, stockee, factures) {
  if (!bareme) return null
  const memes = stockee && Array.isArray(stockee.factures) && Array.isArray(factures)
    && stockee.factures.length === factures.length
    && stockee.factures.every((v, i) => (parseFloat(v) || 0) === (parseFloat(factures[i]) || 0))
  if (stockee && stockee.descendDesFactures && !stockee.auBaremeSociete && memes) return null
  return bareme
}

export function entreesDeEtat(etat) {
  const entrees = {}
  const stockee = etat.consoStockee
  const factures = Array.isArray(etat.monthly) ? etat.monthly : (stockee?.factures || null)
  if (factures) entrees.factures_mensuelles_reelles = factures.map(v => parseFloat(v) || 0)
  let conso = null
  let auBareme = false
  if (stockee && !stockee.descendDesFactures) conso = stockee.valeur
  if (conso == null && factures) {
    const bareme = baremePourDerivation(etat.bareme, stockee, factures)
    const derivee = consoAnnuelleDepuisFactures(factures, etat.distributeur || 'onee',
      bareme?.tranches, bareme?.chargesFixes)
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
 *   `pompage` (dimensionnement retenu),
 *   `entrees` (entrées réelles de la session), `recommended` (option
 *   effective). Absentes → dérivées de l'état seul.
 * @returns {{lignes: Array, entete: object, etude: object|null}}
 */
export function etatVersEcritures(etat, vif = {}) {
  // AGNR8 — les nombres d'en-tête partent à la forme du serveur
  // (`DecimalField(decimal_places=2)`) : arrondi 2 décimales au demi
  // supérieur, vide ⇒ clé omise (taux) ou effacée (prix cible) ; chaque
  // arrondi est rendu dans `normalisations` pour être dit au vendeur.
  const normalisations = []
  const entete = {
    date_validite: etat.dateValidite || null,
    note: etat.note || null,
    mode_installation: etat.mode,
  }
  const tva = normaliserNombreEntete(etat.tauxTva)
  if (tva.envoye !== null) entete.taux_tva = tva.envoye
  if (tva.change) normalisations.push({ champ: 'taux_tva', tape: tva.tape, envoye: tva.envoye })
  const remise = normaliserNombreEntete(etat.discountPct)
  entete.remise_globale = remise.envoye ?? '0'
  if (remise.change) normalisations.push({ champ: 'remise_globale', tape: remise.tape, envoye: entete.remise_globale })
  const cible = normaliserNombreEntete(etat.prixCible)
  entete.prix_cible_kwc = cible.envoye
  if (cible.change) normalisations.push({ champ: 'prix_cible_kwc', tape: cible.tape, envoye: cible.envoye })
  // QJR624 — l'échéancier ne part que s'il était propre au devis ou touché.
  if (etat.echeancierAEnvoyer) entete.echeancier = saisieVersEcheancier(etat.echeancier)
  // CIQ226 — les conditions partent dans l'en-tête dès que l'écran les porte.
  if (etat.conditions) {
    const servies = new Set(etat.conditionsServies || [])
    for (const [cle, valeur] of Object.entries(conditionsVersEntete(etat.conditions))) {
      if (!estVide(valeur) || servies.has(cle)) entete[cle] = valeur
    }
  }

  const farm = etat.farm || {}
  const etude = projeterEtudeMarche(etat.mode, {
    choix: choixDeEtat(etat, { recommended: vif.recommended }),
    entrees: vif.entrees ?? entreesDeEtat(etat),
    categorie: etat.categorieCommerciale,
    pompageEntrees: etat.mode === 'agricole' ? entreesPompageEcran(etat) : undefined,
    ciEntrees: (etat.mode === 'industriel' || etat.mode === 'commercial') && etat.profilCi
      ? entreesCiV2(etat.profilCi, etat.ctxCi || {
        mode: etat.mode,
        ville: etat.villeCi || null,
        categorie: etat.mode === 'commercial' ? etat.categorieCommerciale : null,
        reponses: etat.mode === 'commercial' ? etat.commercialAnswers : null,
      })
      : undefined,
    tarifDeclare: (etat.mode === 'industriel' || etat.mode === 'commercial')
      ? tarifDeclareDepuisSaisie(etat.tarifSaisie, { aujourdhui: etat.aujourdhui })
      : undefined,
    saisiesEcoCi: (etat.mode === 'industriel' || etat.mode === 'commercial')
      ? saisiesEconomieCi(etat.ecoCi, { aujourdhui: etat.aujourdhui })
      : undefined,
    exploitation: {
      attestation: farm.attestation,
      saisiesEconomie: saisiesEconomiePompage(etat.saisiesEco),
    },
  })

  return {
    lignes: lignesEcranVersPayload(etat.lignes || [], { multiMode: etat.multiMode }),
    entete,
    etude,
    normalisations,
  }
}

/**
 * AGNR8 — un nombre d'en-tête tapé → le texte que le serveur accepte (2
 * décimales, arrondi au demi supérieur, calculé sur le TEXTE décimal : jamais
 * l'erreur binaire de `12.345 * 100`). Vide ⇒ `envoye: null`. Illisible ⇒
 * `envoye: null` et `change: true` (le vendeur l'apprend, jamais un 400).
 */
export function normaliserNombreEntete(valeur) {
  if (valeur === null || valeur === undefined) return { tape: valeur, envoye: null, change: false }
  const tape = String(valeur).trim()
  if (tape === '') return { tape, envoye: null, change: false }
  // Déjà acceptable (au plus 2 décimales, point) : envoyé tel que tapé.
  if (/^-?\d+(\.\d{1,2})?$/.test(tape)) return { tape, envoye: tape, change: false }
  const m = /^([+-]?)(\d*)(?:[.,](\d*))?$/.exec(tape.replace(/\s/g, ''))
  if (!m || (m[2] === '' && !(m[3] || ''))) return { tape, envoye: null, change: true }
  const negatif = m[1] === '-'
  const entier = m[2] || '0'
  const frac = m[3] || ''
  let centimes = BigInt(entier) * 100n + BigInt((frac + '00').slice(0, 2))
  if (frac.length > 2 && Number(frac[2]) >= 5) centimes += 1n
  const abs = centimes.toString().padStart(3, '0')
  const texteAbs = `${abs.slice(0, -2)}.${abs.slice(-2)}`
  const envoye = negatif && centimes > 0n ? `-${texteAbs}` : texteAbs
  return { tape, envoye, change: Number(envoye) !== Number(tape.replace(/\s/g, '').replace(',', '.')) }
}
