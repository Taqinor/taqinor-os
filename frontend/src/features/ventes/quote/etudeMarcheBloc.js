// QJR542 — LA projection « étude du marché → clés etude_params légales ».
//
// Déplacement PUR du corps de `blocEtudeMarche` (DevisGenerator.jsx) : une
// seule fonction, sans état React, qui ne laisse sortir QUE des clés ECRAN
// déclarées par `apps/ventes/domain/etude_schema.py` (le schéma refuse en 400
// toute autre clé de tête). Les objets BRUTS de `computeEtudeIndustrielle`
// (solar.js) et de `buildEtudePompage` (autoQuote.js) portent des clés hors
// schéma (kwc, prix_kwc, economies_annuelles…) : ils ne doivent jamais partir
// tels quels — ils passent par ici. Le générateur ET le devis automatique
// (QJR543) appellent cette même fonction : jamais une seconde liste de clés.
//
// Entrées :
//   mode               'industriel' | 'commercial' | 'agricole' | autre (résidentiel)
//   etude              l'étude I/C calculée par l'écran (industriel / commercial)
//   choix              les CHOIX de l'écran (scenario, recommended_option, nombre_proprietes)
//   entrees            fonction (consoDejaConnue) => entrées réelles, ou objet déjà calculé
//   partDiurne         part diurne du curseur industriel (%)
//   tensionRaccordement, repartitionMt   raccordement et répartition horaire TELLE QUE SAISIE
//   categorie, reponses                  catégorie commerciale + réponses du questionnaire
//   pompage            objet de `buildEtudePompage` (ou {} si aucune pompe retenue)
//   saisiePompage      { hmt, debit, heures, typePompe, alim, profondeur, distance }
//   exploitation       { irrigation, region, crop, surfaceHa, hmtStatic, hmtDrawdown,
//                        saisiesEconomie } — AGR212 : l'énergie et la dépense
//                        DÉCLARÉES partent dans `saisies_economie_pompage`
//                        (contrat economie_pompage.json) ; plus jamais
//                        `current_fuel` / `fuel_spend_current`, plus jamais × 12.
import { COMMERCIAL_CATEGORY_QUESTIONS } from '../solar.js'

const nombre = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : null
}

const resoudreEntrees = (entrees, consoDejaConnue) => (
  typeof entrees === 'function' ? entrees(consoDejaConnue) : (entrees || {})
)

// QXMT — la répartition horaire TELLE QUE SAISIE, ou `null` (règle Z2 : un
// site repassé en BT n'a plus de répartition MT, on la RETIRE au lieu de
// laisser traîner celle d'hier). Rien de rempli ⇒ `null` aussi : l'étude MT
// omet alors économies et payback plutôt que d'inventer un barème.
export const repartitionMtSaisie = (tensionRaccordement, repartitionMt) => {
  if (tensionRaccordement !== 'mt') return null
  const parts = {}
  for (const creneau of ['pointe', 'pleines', 'creuses']) {
    const n = parseFloat((repartitionMt || {})[creneau])
    if (Number.isFinite(n)) parts[creneau] = n
  }
  return Object.keys(parts).length ? parts : null
}

export function projeterEtudeMarche(mode, {
  etude, choix = {}, entrees, partDiurne,
  tensionRaccordement, repartitionMt,
  categorie, reponses = {},
  pompage, saisiePompage = {}, exploitation = {},
} = {}) {
  if (mode === 'industriel' || mode === 'commercial') {
    const e = etude || {}
    const bloc = {
      ...choix,
      ...resoudreEntrees(entrees, nombre(e.conso_annuelle)),
      taux_autoconso: nombre(e.taux_autoconso),
      taux_couverture: nombre(e.taux_couverture),
      payback: nombre(e.payback),
      injection_kwh_an: nombre(e.injection_kwh_an),
      injection_dh_an: nombre(e.injection_dh_an),
      // QJR579 (contrat QJR510) — le kWc pour lequel CES dérivées ont été
      // calculées : base de la garde de fraîcheur (QJR625). Nul sans étude.
      etude_kwc_base: nombre(e.kwc),
      // QJR528 — la part diurne du curseur INDUSTRIEL (entrée de l'étude) :
      // relue par `?edit=`, sinon la réouverture remettait le défaut et
      // réécrivait taux / payback. Commercial : dérivée de la catégorie
      // (`commercialDayShare`), rien à écrire.
      part_diurne_pct: mode === 'industriel' ? nombre(partDiurne) : undefined,
      // QXMT — raccordement du site + répartition horaire : le mappeur
      // `?edit=` les relit, donc elles doivent être PERSISTÉES, sinon un
      // devis MT rouvert repartait silencieusement au barème BT. On stocke
      // ce que le vendeur a TAPÉ (l'entrée), pas la répartition normalisée
      // par l'étude : c'est la forme que le formulaire réinjecte.
      tension_raccordement: tensionRaccordement || null,
      repartition_mt: repartitionMtSaisie(tensionRaccordement, repartitionMt),
    }
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
    // MÊME dérivation que l'aperçu écran et que le devis auto
    // (`buildEtudePompage`) : une seule formule, jamais deux chiffres qui
    // pourraient diverger. Seules les clés du schéma en sortent, typées.
    const p = pompage || {}
    const s = saisiePompage
    const x = exploitation
    return {
      ...choix,
      ...resoudreEntrees(entrees, null),
      // DÉRIVÉES du dimensionnement (propriétaire ECRAN au schéma).
      pompe_cv: nombre(p.pompe_cv),
      pompe_kw: nombre(p.pompe_kw),
      debit_hmt_m3h: nombre(p.debit_hmt_m3h),
      m3_jour: nombre(p.m3_jour),
      champ_kwc: nombre(p.champ_kwc),
      // ENTRÉES du vendeur, prises à l'ÉTAT de l'écran (pas au
      // dimensionnement) : ce sont elles que le mappeur `?edit=` réinjecte
      // dans le formulaire, et elles existent même quand aucune pompe à
      // courbe ne peut être retenue.
      hmt_m: nombre(s.hmt),
      debit_souhaite_m3h: nombre(s.debit),
      heures_pompage: nombre(s.heures),
      type_pompe: s.typePompe || null,
      alim: s.alim || null,
      profondeur_m: nombre(s.profondeur),
      distance_m: nombre(s.distance),
      // Exploitation guidée (toutes optionnelles, toutes relues par `?edit=`).
      irrigation_method: x.irrigation || null,
      region: x.region || null,
      crop: x.crop || null,
      surface_ha: nombre(x.surfaceHa),
      // AGR212 — `null` = rien de déclaré : la clé est RETIRÉE (Z2), jamais
      // un « butane » par défaut.
      saisies_economie_pompage: x.saisiesEconomie || null,
      hmt_static: nombre(x.hmtStatic),
      hmt_drawdown: nombre(x.hmtDrawdown),
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
      valeur: e.energie, provenance: { origine: 'saisie', detail: null, date },
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

/** Inverse : `saisies_economie_pompage` stocké → état d'écran (`?edit=`). */
export function ecoDepuisSaisies(saisies) {
  const s = saisies && typeof saisies === 'object' ? saisies : null
  if (!s) return { ...ECO_POMPAGE_VIDE }
  const c = s.consommation || {}
  const f = s.facture_reseau || {}
  return {
    ...ECO_POMPAGE_VIDE,
    energie: s.energie_actuelle?.valeur || '',
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
