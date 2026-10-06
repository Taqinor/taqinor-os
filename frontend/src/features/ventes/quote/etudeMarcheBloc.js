// QJR542 — LA projection « étude du marché → clés etude_params légales ».
//
// Déplacement PUR du corps de `blocEtudeMarche` (DevisGenerator.jsx) : une
// seule fonction, sans état React, qui ne laisse sortir QUE des clés ECRAN
// déclarées par `apps/ventes/domain/etude_schema.py` (le schéma refuse en 400
// toute autre clé de tête). Les objets BRUTS de l'ancienne étude C&I locale
// (solar.js) et de `buildEtudePompage` (autoQuote.js) portent des clés hors
// schéma (kwc, prix_kwc, economies_annuelles…) : ils ne doivent jamais partir
// tels quels — ils passent par ici. Le générateur ET le devis automatique
// (QJR543) appellent cette même fonction : jamais une seconde liste de clés.
//
// Entrées :
//   mode               'industriel' | 'commercial' | 'agricole' | autre (résidentiel)
//   choix              les CHOIX de l'écran (scenario, recommended_option, nombre_proprietes)
//   entrees            fonction (consoDejaConnue) => entrées réelles, ou objet déjà calculé
//   categorie, reponses                  catégorie commerciale + réponses du questionnaire
//   ciEntrees          CIQ125 — les ENTRÉES C&I v2 déjà mises à la forme du contrat
//                        (`entreesCiV2` de profilCi.js).
//   pompageEntrees     AGR130 — l'état du corps de l'aperçu pompage (forme du contrat
//                        etude_pompage_preview.json, nombres éventuellement en texte) ;
//                        seules les ENTRÉES v2 partent (`entreesPompageV2`).
//   exploitation       { saisiesEconomie, attestation } — AGR212 : l'énergie et la dépense
//                        DÉCLARÉES partent dans `saisies_economie_pompage`
//                        (contrat economie_pompage.json) ; plus jamais
//                        `current_fuel` / `fuel_spend_current`, plus jamais × 12.
//                        AGR218 : `attestation` {attestee, le, signataire} →
//                        `attestation_usage_agricole`.
import { COMMERCIAL_CATEGORY_QUESTIONS, ttcFromHt, tauxTvaOf } from '../solar.js'

const nombre = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : null
}

const resoudreEntrees = (entrees, consoDejaConnue) => (
  typeof entrees === 'function' ? entrees(consoDejaConnue) : (entrees || {})
)

export function projeterEtudeMarche(mode, {
  choix = {}, entrees,
  categorie, reponses = {},
  pompageEntrees, exploitation = {}, ciEntrees, tarifDeclare, saisiesEcoCi,
} = {}) {
  if (mode === 'industriel' || mode === 'commercial') {
    // CIQ126 — le navigateur n'envoie QUE les ENTRÉES C&I v2 (contrat
    // `etude_ci_preview.json`, `cles_etude_params_ci_v2.entrees`) : les
    // dérivées (`etude_ci`, `production_figee`) sont écrites par le serveur
    // (propriétaire `moteur_ci`). Plus aucune clé ÉCRAN v1 (`a_retirer_v1` :
    // taux_autoconso, taux_couverture, payback, part_diurne_pct,
    // etude_kwc_base, injection_kwh_an, injection_dh_an), ni le raccordement
    // et la répartition MT v1 (tension_raccordement, repartition_mt).
    const bloc = {
      ...choix,
      ...(ciEntrees || {}),
    }
    // CIQ222 — le tarif DÉCLARÉ de la facture (contrat `tarifs_ci.json`) ;
    // `null` = rien de saisi, la clé est retirée (grille ONEE en repli).
    if (tarifDeclare !== undefined) bloc.tarif_declare = tarifDeclare
    // CIQ223 — les saisies de l'économie C&I (contrat `economie_ci.json`).
    if (saisiesEcoCi !== undefined) bloc.saisies_economie_ci = saisiesEcoCi
    if (mode === 'commercial') {
      // QX44 — la catégorie ET ses réponses (clés snake_case à plat, comme
      // le mappeur `?edit=` les relit : `e[q.key]`). Coercition de type
      // IDENTIQUE à celle d'avant, jamais de `prix_achat`.
      bloc.categorie_commerciale = categorie || null
      for (const q of (COMMERCIAL_CATEGORY_QUESTIONS[categorie] || [])) {
        const brut = reponses[q.key]
        if (brut === undefined || brut === '' || brut === null) continue
        bloc[q.key] = q.type === 'number'
          ? (parseFloat(brut) || 0)
          : q.type === 'bool' ? !!brut : String(brut)
      }
    }
    return bloc
  }
  if (mode === 'agricole') {
    // AGR130 (D-AGR-1 / D-AGR-13) — le navigateur n'envoie QUE les ENTRÉES v2
    // du contrat `etude_pompage_preview.json` (`cles_etude_params_v2.entrees`) :
    // les dérivées (pompe retenue, m³/jour, champ, kit…) sont calculées par le
    // rafraîchisseur serveur (AGR123) et refusées en 400 si l'écran les écrit.
    const x = exploitation
    return {
      ...choix,
      ...resoudreEntrees(entrees, null),
      ...entreesPompageV2(pompageEntrees),
      // AGR212 — `null` = rien de déclaré : la clé est RETIRÉE (Z2), jamais
      // un « butane » par défaut.
      saisies_economie_pompage: x.saisiesEconomie || null,
      // AGR218 (contrat AGR200) — l'attestation d'usage agricole SAISIE ;
      // `null` = rien de coché ni saisi : la clé est RETIRÉE (Z2).
      attestation_usage_agricole: attestationUsageAgricole(x.attestation),
    }
  }
  // Résidentiel : le serveur est propriétaire de son ÉTUDE — mais pas des
  // CHOIX du vendeur ni des entrées réelles qu'il vient de taper (arbitrage
  // « zéro perte »). Objet vide ⇒ `null` (aucun appel du tout).
  const res = { ...choix, ...resoudreEntrees(entrees, null) }
  return Object.keys(res).length ? res : null
}


// ── AGR212 — les saisies DÉCLARÉES de l'économie de pompage ────────────────
// État d'écran (texte tel que tapé) ⇄ forme `saisies_economie_pompage` du
// contrat `apps/ventes/contract_samples/economie_pompage.json`. Aucun défaut :
// une énergie non choisie est ABSENTE ; aucune dépense n'est jamais
// multipliée par 12 (le serveur compte chaque mois coché).
export const ECO_POMPAGE_VIDE = Object.freeze({
  energie: '', quantite: '', unite: '', periode: '', joursSemaine: '',
  prix: '', dateDeclaration: '', mois: null, moisProvenance: null,
  energieProvenance: null,
  confirme: false, factureMontant: '', facturePeriodicite: '',
  facturePartFixe: '', entretien: '', coherenceConfirmee: false,
  interne: Object.freeze({ taux_actualisation: null, pret: null }),
})

const CARBURANTS = ['butane', 'diesel']

const vide = (v) => v === '' || v === null || v === undefined

const texteNet = (v) => (vide(v) ? '' : String(v).trim())

// Virgule décimale lue comme un point (saisie FR), jamais arrondie.
const nombreSaisi = (v) => (vide(v) ? null : nombre(String(v).replace(',', '.')))

/** AGR214 — `{valeur, source}` du taux d'actualisation, ou `null`. */
export function tauxActualisation(saisie) {
  if (!saisie || vide(saisie.valeur)) return null
  return { valeur: nombreSaisi(saisie.valeur), source: texteNet(saisie.source) }
}

const CHAMPS_PRET_NUMERIQUES = ['principal_mad', 'taux_annuel_pct', 'duree_mois', 'differe_mois']

/** AGR214 — le prêt saisi (offre écrite), ou `null` si rien n'est rempli. */
export function pretInterne(saisie) {
  if (!saisie) return null
  const rempli = [...CHAMPS_PRET_NUMERIQUES, 'type_pret', 'source']
    .some((k) => !vide(saisie[k]))
  if (!rempli) return null
  const pret = {}
  for (const k of CHAMPS_PRET_NUMERIQUES) pret[k] = nombreSaisi(saisie[k])
  pret.type_pret = texteNet(saisie.type_pret) || null
  pret.source = texteNet(saisie.source)
  return pret
}

/**
 * `eco` (état d'écran) → `saisies_economie_pompage`, ou `null` si rien n'est
 * déclaré. `moisCalendrier` = mois où le besoin servi par l'aperçu (AGR2) est
 * > 0 pour une culture : pré-cochés, provenance « calendrier de la culture »
 * tant que le vendeur n'a ni touché les cases ni coché « confirmé ».
 */
export function saisiesEconomiePompage(eco, { moisCalendrier = null, aujourdhui = '' } = {}) {
  const e = { ...ECO_POMPAGE_VIDE, ...(eco || {}) }
  const date = e.dateDeclaration || aujourdhui || null
  const carburant = CARBURANTS.includes(e.energie)
  let mois = null
  if (Array.isArray(e.mois)) {
    mois = {
      mois: [...e.mois].map(Number).sort((a, b) => a - b),
      provenance: e.moisProvenance
        || { origine: 'saisie', detail: null, date },
    }
  } else if (Array.isArray(moisCalendrier) && moisCalendrier.length) {
    mois = {
      mois: [...moisCalendrier].map(Number).sort((a, b) => a - b),
      provenance: e.confirme
        ? { origine: 'saisie', detail: null, date }
        : { origine: 'calculee', detail: 'calendrier_culture', date },
    }
  }
  const out = {}
  if (e.energie) {
    out.energie_actuelle = {
      valeur: e.energie,
      // AGR420 — une énergie reprise du lead garde sa provenance `lead`.
      provenance: e.energieProvenance || { origine: 'saisie', detail: null, date },
    }
  }
  out.consommation = carburant && !vide(e.quantite) ? {
    quantite: nombre(e.quantite),
    unite: e.unite || null,
    periode: e.periode || null,
    jours_irrigation_par_semaine: e.periode === 'jour_irrigation'
      ? nombre(e.joursSemaine) : null,
    saisi_le: date,
  } : null
  out.depense_unitaire_payee = carburant && !vide(e.prix)
    ? { valeur: nombre(e.prix), saisi_le: date } : null
  out.facture_reseau = e.energie === 'electrique' && !vide(e.factureMontant) ? {
    montant_mad: nombre(e.factureMontant),
    periodicite: e.facturePeriodicite || null,
    part_fixe_mad_mois: nombre(e.facturePartFixe),
    saisi_le: date,
  } : null
  out.mois_irrigation = mois
  out.entretien_paye_mad_an = !vide(e.entretien)
    ? { valeur: nombre(e.entretien), saisi_le: date } : null
  out.coherence_confirmee = Boolean(e.coherenceConfirmee)
  // AGR214 — saisies INTERNES (volet jamais imprimé) : texte tapé → nombres,
  // rien de rempli ⇒ `null` ; aucun taux par défaut.
  out.taux_actualisation = tauxActualisation(e.interne?.taux_actualisation)
  out.pret = pretInterne(e.interne?.pret)
  const declare = e.energie || out.mois_irrigation || out.entretien_paye_mad_an
    || out.coherence_confirmee || out.taux_actualisation || out.pret
  return declare ? out : null
}

const texte = (v) => (v === null || v === undefined ? '' : String(v))

// AGR420 — seule une provenance AUTRE que « saisi » (lead…) est conservée.
const provenanceNonSaisie = (p) => (
  p && typeof p === 'object' && p.origine && p.origine !== 'saisie' ? p : null)

/** Inverse : `saisies_economie_pompage` stocké → état d'écran (`?edit=`). */
export function ecoDepuisSaisies(saisies) {
  const s = saisies && typeof saisies === 'object' ? saisies : null
  if (!s) return { ...ECO_POMPAGE_VIDE }
  const c = s.consommation || {}
  const f = s.facture_reseau || {}
  return {
    ...ECO_POMPAGE_VIDE,
    energie: s.energie_actuelle?.valeur || '',
    energieProvenance: provenanceNonSaisie(s.energie_actuelle?.provenance),
    quantite: texte(c.quantite),
    unite: c.unite || '',
    periode: c.periode || '',
    joursSemaine: texte(c.jours_irrigation_par_semaine),
    prix: texte(s.depense_unitaire_payee?.valeur),
    dateDeclaration: s.energie_actuelle?.provenance?.date || c.saisi_le
      || s.depense_unitaire_payee?.saisi_le || f.saisi_le
      || s.entretien_paye_mad_an?.saisi_le || s.mois_irrigation?.provenance?.date || '',
    mois: Array.isArray(s.mois_irrigation?.mois) ? [...s.mois_irrigation.mois] : null,
    moisProvenance: s.mois_irrigation?.provenance || null,
    factureMontant: texte(f.montant_mad),
    facturePeriodicite: f.periodicite || '',
    facturePartFixe: texte(f.part_fixe_mad_mois),
    entretien: texte(s.entretien_paye_mad_an?.valeur),
    coherenceConfirmee: Boolean(s.coherence_confirmee),
    interne: { taux_actualisation: s.taux_actualisation ?? null, pret: s.pret ?? null },
  }
}

// ── AGR218 — attestation d'usage exclusivement agricole (contrat AGR200) ──
// État d'écran {attestee, le, signataire} ⇄ `etude_params.attestation_usage_
// agricole`. Saisie, jamais supposée : rien de coché ni saisi ⇒ `null`.
export const ATTESTATION_VIDE = Object.freeze({ attestee: false, le: '', signataire: '' })

/** État d'écran → forme stockée `{attestee, le, signataire}`, ou `null`. */
export function attestationUsageAgricole(saisie) {
  if (!saisie || typeof saisie !== 'object') return null
  const attestee = Boolean(saisie.attestee)
  const le = texteNet(saisie.le) || null
  const signataire = texteNet(saisie.signataire)
  if (!attestee && !le && !signataire) return null
  return { attestee, le, signataire }
}

/** Inverse : la forme stockée → état d'écran (`?edit=`). */
export function attestationDepuisEtude(valeur) {
  if (!valeur || typeof valeur !== 'object') return { ...ATTESTATION_VIDE }
  return {
    attestee: Boolean(valeur.attestee),
    le: valeur.le || '',
    signataire: valeur.signataire || '',
  }
}

// ── AGR130 — les ENTRÉES v2 du pompage (une seule liste, celle du contrat) ──
// Clés de tête persistées dans `etude_params` : le bloc `hmt` du corps s'y
// appelle `hmt_entrees` (la clé `hmt` serait ambiguë avec les dérivées).
const TEXTES_POMPAGE = new Set([
  'mode_pompe', 'mode', 'phases', 'debit_exploitation_origine',
  'debit_exploitation_date', 'materiau', 'crop', 'irrigation', 'region',
  'ville', 'alim', 'type_pompe', 'taille',
])

// '' → null ; texte nommé → texte ; sinon nombre lu (virgule FR), jamais arrondi.
const normaliserPompage = (valeur, cle) => {
  if (Array.isArray(valeur)) return valeur.map((v) => normaliserPompage(v, cle))
  if (valeur && typeof valeur === 'object') {
    const out = {}
    for (const [k, v] of Object.entries(valeur)) out[k] = normaliserPompage(v, k)
    return out
  }
  if (valeur === true || valeur === false) return valeur
  if (vide(valeur)) return null
  if (cle === 'compteur') return valeur === 'oui' ? true : valeur === 'non' ? false : null
  if (TEXTES_POMPAGE.has(cle)) return texteNet(valeur) || null
  return nombreSaisi(valeur)
}

const TAILLES_POMPAGE = ['recommandee', 'inferieure', 'superieure']

/**
 * L'état du corps de l'aperçu (`etatPompageEcran`) → les ENTRÉES v2 de
 * `etude_params` (D-AGR-13). `{}` sans état : aucune clé v1, aucune dérivée.
 * `plaque` n'existe qu'en mode « existante » ; `options_cochees` est toujours
 * une liste ; les identifiants `lead`/`devis` du corps n'y entrent jamais.
 */
export function entreesPompageV2(etat) {
  if (!etat || typeof etat !== 'object') return {}
  const n = normaliserPompage
  const existante = etat.mode_pompe === 'existante'
  return {
    mode_pompe: n(etat.mode_pompe, 'mode_pompe'),
    plaque: existante && etat.plaque ? n(etat.plaque, 'plaque') : null,
    besoin: etat.besoin ? n(etat.besoin, 'besoin') : null,
    source: etat.source ? n(etat.source, 'source') : null,
    hmt_entrees: etat.hmt ? n(etat.hmt, 'hmt') : null,
    alim: n(etat.alim, 'alim'),
    type_pompe: n(etat.type_pompe, 'type_pompe'),
    localisation: etat.localisation ? n(etat.localisation, 'localisation') : null,
    distance_champ_m: n(etat.distance_champ_m, 'distance_champ_m'),
    options_cochees: Array.isArray(etat.options_cochees) ? [...etat.options_cochees] : [],
    taille: TAILLES_POMPAGE.includes(etat.taille) ? etat.taille : null,
  }
}

// ── AGR130 — Auto-remplir : les lignes du KIT serveur, aucune composition JS ──
// `kit` = la réponse de l'aperçu (`kit.inclus` + les `kit.options` cochées).
// `produits` = le catalogue de l'écran (prix de vente HT, TVA du produit) :
// le serveur dit QUOI et COMBIEN, l'écran ne fait que poser le prix du
// produit. Un article au prix à renseigner (`produit: null`) devient une ligne
// SANS produit (jamais enregistrée, jamais chiffrée à 0 comme un article
// gratuit) ; une option dont la quantité est à saisir (`quantite: null`) est
// laissée de côté. Rien n'est inventé.
export function lignesDepuisKit(kit, produits) {
  if (!kit || typeof kit !== 'object') return []
  const cochees = (kit.options || []).filter((o) => o && o.cochee)
  const rows = []
  for (const it of [...(kit.inclus || []), ...cochees]) {
    const quantite = Number(it.quantite)
    if (!Number.isFinite(quantite) || quantite <= 0) continue
    const p = (it.produit == null || it.prix_connu === false) ? null
      : (produits || []).find((x) => String(x.id) === String(it.produit)) || null
    rows.push({
      produit: p ? String(p.id) : '',
      designation: p ? p.nom : (it.designation || it.libelle || '') + (it.designation ? '' : ' — prix à renseigner'),
      quantite,
      prix_unit_ttc: p ? ttcFromHt(p.prix_vente, tauxTvaOf(p)) : 0,
      taux_tva: p ? tauxTvaOf(p) : 20,
    })
  }
  return rows
}

// ── CIQ222 — le tarif de SA facture (contrat `tarifs_ci.json`, `tarif_declare`) ──
// État d'écran (texte tel que tapé) → `etude_params.tarif_declare`. Aucun
// défaut, aucun nombre corrigé ; rien de saisi ⇒ `null` (la clé est retirée :
// le moteur retombe sur la grille officielle ONEE, annoncée sous la carte).
export const TARIF_SAISIE_VIDE = Object.freeze({
  contrat: '', baseTarifs: '', optionBiHoraire: false,
  pointe: '', pleines: '', creuses: '', primeFixe: '', puissance: '',
  dateFacture: '', provenance: '', saisiLe: '',
})

/** `true` si un prix ou un choix de contrat a été saisi. */
export const tarifSaisi = (t) => Boolean(t) && Object.entries(TARIF_SAISIE_VIDE)
  .some(([k, vide0]) => k !== 'saisiLe' && t[k] !== undefined && t[k] !== vide0)

export function tarifDeclareDepuisSaisie(saisie, { aujourdhui = '' } = {}) {
  const t = { ...TARIF_SAISIE_VIDE, ...(saisie || {}) }
  if (!tarifSaisi(t)) return null
  const mt = t.contrat === 'mt_general' ? {
    tarif_pointe: nombreSaisi(t.pointe),
    tarif_pleines: nombreSaisi(t.pleines),
    tarif_creuses: nombreSaisi(t.creuses),
    prime_fixe_kva_an: nombreSaisi(t.primeFixe),
    puissance_souscrite_kva: nombreSaisi(t.puissance),
  } : null
  return {
    contrat: t.contrat || null,
    option_bi_horaire: t.contrat === 'bt_force_motrice' ? Boolean(t.optionBiHoraire) : false,
    base_tarifs: t.baseTarifs || null,
    mt,
    bt: null,
    date_facture: t.dateFacture || null,
    provenance: t.provenance || null,
    saisi_le: t.saisiLe || aujourdhui || null,
  }
}

/**
 * Le 400 du serveur (`detail` qui nomme « etude_params.tarif_declare.<champ> »)
 * → `{ '<champ>': message }`, pour l'afficher SOUS le champ nommé.
 */
export function erreursTarifDeclare(detail) {
  const messages = Array.isArray(detail) ? detail : (typeof detail === 'string' ? [detail] : [])
  const out = {}
  for (const brut of messages) {
    for (const m of String(brut).matchAll(/etude_params\.tarif_declare\.([a-z_.0-9[\]]+)/g)) {
      if (!out[m[1]]) out[m[1]] = String(brut)
    }
  }
  return out
}

// ── CIQ223/CIQ224 — les saisies de l'économie C&I (contrat `economie_ci.json`,
// `saisies_economie_ci`) : état d'écran (forme du contrat, nombres en texte tels
// que tapés) → `etude_params.saisies_economie_ci`. Aucun défaut : ni taux, ni
// parcours d'aide, ni TVA supposés ; rien de saisi ⇒ `null` (clé retirée).
export const ECO_CI_VIDE = Object.freeze({
  tva_recuperable: null,
  taux_actualisation_client: null,
  revente_demandee: false,
  parcours_aide: null,
  offre_financement: null,
  offre_cse_concurrente: null,
  fiscalite_client: null,
})

const NOMBRES_ECO_CI = new Set([
  'valeur_pct', 'montant_finance_mad', 'apport_mad', 'duree_mois', 'echeance_mad',
  'frais_mad', 'taux_annuel_pct', 'valeur_residuelle_mad', 'tarif_kwh_ht', 'duree_ans',
  'indexation_pct_an', 'taux_is_pct', 'amortissement_coefficient',
])

// Un sous-objet saisi → forme du contrat ; entièrement vide ⇒ `null`.
function objetEcoCi(o) {
  if (!o || typeof o !== 'object') return null
  const out = {}
  let rempli = false
  for (const [k, v] of Object.entries(o)) {
    if (NOMBRES_ECO_CI.has(k)) out[k] = nombreSaisi(v)
    else if (typeof v === 'boolean') out[k] = v
    else out[k] = texteNet(v) || null
    if (out[k] !== null && out[k] !== false && k !== 'saisi_le') rempli = true
  }
  return rempli ? out : null
}

export function saisiesEconomieCi(eco, { aujourdhui = '' } = {}) {
  const e = { ...ECO_CI_VIDE, ...(eco || {}) }
  const dater = (o) => (o ? { ...o, saisi_le: o.saisi_le || aujourdhui || null } : null)
  const out = {
    tva_recuperable: dater(objetEcoCi(e.tva_recuperable)),
    taux_actualisation_client: dater(objetEcoCi(e.taux_actualisation_client)),
    revente_demandee: Boolean(e.revente_demandee),
    parcours_aide: texteNet(e.parcours_aide) || null,
    offre_financement: objetEcoCi(e.offre_financement),
    offre_cse_concurrente: objetEcoCi(e.offre_cse_concurrente),
    fiscalite_client: objetEcoCi(e.fiscalite_client),
  }
  const declare = Object.entries(out).some(([, v]) => v !== null && v !== false)
  return declare ? out : null
}
