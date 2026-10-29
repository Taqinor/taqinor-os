// AGR127 — fonctions PURES de l'aperçu pompage serveur (imports relatifs seulement : elles
// tournent sous `node --test`, voir etudePompagePreview.test.mjs).
//
// Contrat partagé : `backend/django_core/apps/ventes/contract_samples/
// etude_pompage_preview.json` (AGR2). L'écran ne CALCULE rien : il construit
// le corps à partir de ce que le vendeur a TAPÉ, l'envoie à
// `POST /ventes/etude-pompage/preview/` (AGR121) et affiche la réponse.
//
// RÈGLES :
//   1. aucune valeur par défaut n'est posée ici — un champ vide part `null`
//      (règle « un défaut n'est jamais enregistré comme une saisie ») ;
//   2. aucun nombre n'est arrondi ni « corrigé » : la saisie part telle quelle
//      (seule la virgule décimale est lue comme un point) ;
//   3. tant qu'il manque l'essentiel (le besoin en eau ET la hauteur), le
//      corps vaut `null` : AUCUN appel réseau ;
//   4. toutes les alertes du serveur sont rendues, aucune n'est filtrée.

import {
  nombreOuNull, texteOuNull, creerLibelleProvenance, alertesDuServeur,
} from './etudePreviewCommun.js'

export { nombreOuNull }

// Les champs NUMÉRIQUES du corps, par bloc (les autres sont du texte).
const NUM_PLAQUE = ['kw', 'tension_v', 'cv', 'courant_a']
const NUM_BESOIN = ['volume_m3_jour', 'debit_souhaite_m3h', 'mois_pointe',
  'debit_actuel_m3h', 'heures_actuelles_jour']
const NUM_SOURCE = ['debit_exploitation_m3h', 'debit_autorise_m3h',
  'volume_annuel_autorise_m3', 'niveau_statique_m', 'niveau_dynamique_m',
  'rabattement_m', 'profondeur_forage_m', 'diametre_tubage_mm',
  'profondeur_calage_m', 'volume_reservoir_m3']
const TXT_SOURCE = ['debit_exploitation_origine', 'debit_exploitation_date']
const NUM_HMT = ['saisie_m', 'denivele_m', 'pertes_singulieres_m',
  'pression_service_bar']
const NUM_CONDUITE = ['diametre_interieur_mm', 'longueur_m', 'c_hazen_williams']

// AGQ27 — les champs PROPRES à un mode de besoin (absents des autres modes).
const CHAMPS_PAR_MODE_BESOIN = {
  volume_declare: ['volume_m3_jour'],
  pompe_actuelle: ['debit_actuel_m3h', 'heures_actuelles_jour'],
}

const MODES_POMPE = ['neuve', 'existante']
const TAILLES = ['recommandee', 'inferieure', 'superieure']

const positif = (v) => {
  const n = nombreOuNull(v)
  return n !== null && n > 0
}

const blocNumerique = (src, numeriques, textes = []) => {
  const s = src || {}
  const out = {}
  for (const k of numeriques) out[k] = nombreOuNull(s[k])
  for (const k of textes) out[k] = texteOuNull(s[k])
  return out
}

const compteur = (v) => {
  if (v === true || v === false) return v
  if (v === 'oui') return true
  if (v === 'non') return false
  return null
}

function construireBesoin(b = {}) {
  const cultures = Array.isArray(b.cultures) ? b.cultures
    .filter((c) => c && texteOuNull(c.crop))
    .map((c) => ({
      crop: texteOuNull(c.crop),
      surface_ha: nombreOuNull(c.surface_ha),
      irrigation: texteOuNull(c.irrigation),
    })) : []
  const numeriques = blocNumerique(b, NUM_BESOIN)
  // AGQ27 (C-AGQ-026) — seuls les champs du mode CHOISI partent : une valeur
  // tapée sous un autre mode (pompe actuelle, volume) part `null`, jamais en
  // valeur fantôme. Débit souhaité, mois de pointe, cultures et région
  // restent (servis à côté, quel que soit le mode).
  for (const [mode, champs] of Object.entries(CHAMPS_PAR_MODE_BESOIN)) {
    if (b.mode !== mode) for (const champ of champs) numeriques[champ] = null
  }
  return {
    mode: texteOuNull(b.mode),
    ...numeriques,
    cultures,
    region: texteOuNull(b.region),
  }
}

function construireHmt(h = {}) {
  const c = h.conduite || {}
  const conduiteVide = !texteOuNull(c.materiau)
    && NUM_CONDUITE.every((k) => nombreOuNull(c[k]) === null)
  return {
    ...blocNumerique(h, NUM_HMT),
    conduite: conduiteVide ? null : {
      materiau: texteOuNull(c.materiau),
      ...blocNumerique(c, NUM_CONDUITE),
    },
  }
}

/**
 * Rejeu live AGQ41 (24/10) — PARITÉ avec le serveur (`pompage.py::_besoin`) :
 * sans mode choisi (ou mode `debit_souhaite`), le besoin en eau vient du seul
 * DÉBIT SOUHAITÉ × les heures-pic du mois. Le corps n'envoie alors que ce que
 * le serveur lit (`besoin.debit_souhaite_m3h`) : `construireBesoin` met déjà à
 * `null` le volume et la pompe actuelle hors de leur mode (AGQ27).
 */
export function besoinDepuisDebitSouhaite(besoin) {
  const b = besoin || {}
  return (!b.mode || b.mode === 'debit_souhaite') && positif(b.debit_souhaite_m3h)
}

/** Le besoin en eau est-il exprimé (selon son mode) ? */
export function besoinExprime(besoin) {
  const b = besoin || {}
  if (besoinDepuisDebitSouhaite(b)) return true
  if (b.mode === 'volume_declare') return positif(b.volume_m3_jour)
  if (b.mode === 'pompe_actuelle') {
    return positif(b.debit_actuel_m3h) && positif(b.heures_actuelles_jour)
  }
  if (b.mode === 'agronomique') {
    return (b.cultures || []).some((c) => texteOuNull(c?.crop)
      && positif(c?.surface_ha)) && Boolean(texteOuNull(b.region))
  }
  return false
}

/** La hauteur est-elle connue (HMT saisie, ou un niveau d'eau mesuré) ? */
export function hauteurConnue(hmt, source) {
  if (positif((hmt || {}).saisie_m)) return true
  const s = source || {}
  return positif(s.niveau_dynamique_m)
    || (positif(s.niveau_statique_m) && nombreOuNull(s.rabattement_m) !== null)
}

/** Ce qui manque pour lancer l'aperçu (libellés FR), `[]` si rien. */
export function manquantsPompage(etat) {
  const e = etat || {}
  const manque = []
  if (!MODES_POMPE.includes(e.mode_pompe)) manque.push('le cas de pompe (neuve ou existante)')
  if (!besoinExprime(e.besoin)) manque.push('le besoin en eau')
  if (!hauteurConnue(e.hmt, e.source)) manque.push('la hauteur (HMT ou niveau d\'eau)')
  return manque
}

/**
 * Le corps du contrat `etude_pompage_preview.json`, ou `null` tant qu'il
 * manque l'essentiel (aucun appel). `etat` suit la forme du corps (les
 * nombres peuvent arriver en texte, tels que tapés).
 */
export function construireCorpsPompage(etat) {
  if (!etat || manquantsPompage(etat).length) return null
  const e = etat
  const existante = e.mode_pompe === 'existante'
  const plaque = existante ? {
    ...blocNumerique(e.plaque, NUM_PLAQUE),
    phases: texteOuNull((e.plaque || {}).phases),
  } : null
  const loc = e.localisation || {}
  const source = blocNumerique(e.source, NUM_SOURCE, TXT_SOURCE)
  source.compteur = compteur((e.source || {}).compteur)
  const corps = {
    mode_pompe: e.mode_pompe,
    plaque: plaque && {
      kw: plaque.kw, tension_v: plaque.tension_v, phases: plaque.phases,
      cv: plaque.cv, courant_a: plaque.courant_a,
    },
    besoin: construireBesoin(e.besoin),
    source: {
      debit_exploitation_m3h: source.debit_exploitation_m3h,
      debit_exploitation_origine: source.debit_exploitation_origine,
      debit_exploitation_date: source.debit_exploitation_date,
      debit_autorise_m3h: source.debit_autorise_m3h,
      volume_annuel_autorise_m3: source.volume_annuel_autorise_m3,
      compteur: source.compteur,
      niveau_statique_m: source.niveau_statique_m,
      niveau_dynamique_m: source.niveau_dynamique_m,
      rabattement_m: source.rabattement_m,
      profondeur_forage_m: source.profondeur_forage_m,
      diametre_tubage_mm: source.diametre_tubage_mm,
      profondeur_calage_m: source.profondeur_calage_m,
      volume_reservoir_m3: source.volume_reservoir_m3,
    },
    hmt: construireHmt(e.hmt),
    alim: texteOuNull(e.alim),
    type_pompe: texteOuNull(e.type_pompe),
    localisation: {
      ville: texteOuNull(loc.ville),
      lat: nombreOuNull(loc.lat),
      lon: nombreOuNull(loc.lon),
    },
    distance_champ_m: nombreOuNull(e.distance_champ_m),
    options_cochees: Array.isArray(e.options_cochees)
      ? [...e.options_cochees] : [],
    taille: TAILLES.includes(e.taille) ? e.taille : 'recommandee',
  }
  if (nombreOuNull(e.lead) !== null) corps.lead = nombreOuNull(e.lead)
  if (nombreOuNull(e.devis) !== null) corps.devis = nombreOuNull(e.devis)
  if (nombreOuNull(e.client) !== null) corps.client = nombreOuNull(e.client)
  return corps
}

// ── AGR128 — l'état d'écran du générateur agricole ────────────────────────
// Les champs NOUVEAUX (cas de pompe, besoin, point d'eau, HMT détaillée) :
// TOUS vides au départ — aucun défaut n'est jamais enregistré comme une
// saisie. Les champs historiques de l'écran (CV, HMT saisie, débit souhaité,
// profondeur, distance, niveau statique, rabattement, culture…) restent leurs
// propres états et sont RECOMPOSÉS dans la forme du corps par
// `etatPompageEcran` — une seule correspondance, testée.
export const POMPAGE_SAISIE_VIDE = Object.freeze({
  mode_pompe: '',
  plaque: Object.freeze({ kw: '', tension_v: '', phases: '', courant_a: '' }),
  besoin: Object.freeze({
    mode: '', volume_m3_jour: '', mois_pointe: '', debit_actuel_m3h: '',
    heures_actuelles_jour: '',
  }),
  source: Object.freeze({
    debit_exploitation_m3h: '', debit_exploitation_origine: '',
    debit_exploitation_date: '', debit_autorise_m3h: '',
    volume_annuel_autorise_m3: '', compteur: '', niveau_dynamique_m: '',
    diametre_tubage_mm: '', profondeur_calage_m: '', volume_reservoir_m3: '',
  }),
  hmt: Object.freeze({
    detail: false, denivele_m: '', pertes_singulieres_m: '',
    pression_service_bar: '',
    conduite: Object.freeze({ materiau: '', diametre_interieur_mm: '', longueur_m: '' }),
  }),
  options_cochees: Object.freeze([]),
  taille: '',
})

/** Pose `valeur` au chemin `a.b.c` d'une saisie (copie, jamais en place). */
export function poserSaisie(saisie, chemin, valeur) {
  const cles = chemin.split('.')
  const racine = { ...(saisie || {}) }
  let noeud = racine
  for (let i = 0; i < cles.length - 1; i += 1) {
    noeud[cles[i]] = { ...(noeud[cles[i]] || {}) }
    noeud = noeud[cles[i]]
  }
  noeud[cles[cles.length - 1]] = valeur
  return racine
}

/**
 * La forme du corps (AGR127) depuis l'état de l'écran : `saisie` (les blocs
 * nouveaux) + `ecran` (les états historiques). Rien n'est inventé : un champ
 * vide reste vide (et part `null`).
 */
export function etatPompageEcran(saisie, ecran = {}) {
  const s = saisie || POMPAGE_SAISIE_VIDE
  const e = ecran || {}
  const b = s.besoin || {}
  const h = s.hmt || {}
  const culture = (e.farmCrop || e.farmSurfaceHa)
    ? [{ crop: e.farmCrop || '', surface_ha: e.farmSurfaceHa ?? '',
        irrigation: e.farmIrrigation || '' }]
    : []
  return {
    mode_pompe: s.mode_pompe || '',
    plaque: { ...(s.plaque || {}), cv: e.pompeCv ?? '' },
    besoin: {
      mode: b.mode || '',
      volume_m3_jour: b.volume_m3_jour ?? '',
      debit_souhaite_m3h: e.pompeDebit ?? '',
      mois_pointe: b.mois_pointe ?? '',
      debit_actuel_m3h: b.debit_actuel_m3h ?? '',
      heures_actuelles_jour: b.heures_actuelles_jour ?? '',
      cultures: culture,
      region: e.farmRegion || '',
    },
    source: {
      ...(s.source || {}),
      niveau_statique_m: e.farmHmtStatic ?? '',
      rabattement_m: e.farmHmtDrawdown ?? '',
      profondeur_forage_m: e.pompeProfondeur ?? '',
    },
    hmt: {
      saisie_m: e.pompeHmt ?? '',
      denivele_m: h.detail ? (h.denivele_m ?? '') : '',
      conduite: h.detail ? { c_hazen_williams: '', ...(h.conduite || {}) } : null,
      pertes_singulieres_m: h.detail ? (h.pertes_singulieres_m ?? '') : '',
      pression_service_bar: h.detail ? (h.pression_service_bar ?? '') : '',
    },
    alim: e.pompeAlim || '',
    type_pompe: e.pompeType || '',
    // AGQ26 — ville ET GPS du lead quand l'écran les a (jamais inventés).
    localisation: { ville: e.ville || '', lat: e.lat ?? '', lon: e.lon ?? '' },
    distance_champ_m: e.pompeDistance ?? '',
    options_cochees: [...(s.options_cochees || [])],
    taille: s.taille || '',
    lead: e.leadId ?? null,
    devis: e.editId ?? null,
    // AGRI-SITE (28/10) — sans lead, le serveur lit le SITE sur la fiche client.
    client: e.clientId ?? null,
  }
}

const LIBELLES_ORIGINE = {
  saisie: 'saisi',
  lead: 'fiche lead',
  reglage_societe: 'réglage société',
  fiche: 'fiche produit',
  pvgis: 'PVGIS',
  calculee: 'calculé',
  estimation: 'estimation',
}
const LIBELLES_DETAIL_LEAD = {
  client: 'déclaré par le client',
  site_web: 'formulaire du site',
  mesure_visite: 'mesuré en visite',
  derive: 'déduit',
}

export const libelleProvenance = creerLibelleProvenance(LIBELLES_ORIGINE, LIBELLES_DETAIL_LEAD)

/**
 * TOUTES les alertes du serveur, dans l'ordre, aucune filtrée (QX48(f) :
 * jamais bloquantes). Une alerte sans message garde son code pour rester
 * visible.
 */
export const alertesAffichables = (reponse) => alertesDuServeur(
  reponse, 'Alerte du moteur de pompage',
)

/**
 * Rejeu live AGQ41 (24/10) — un kit de pompage SANS l'un de ses rôles minimum
 * (variateur, panneaux, structure, installation : `roles_minimum_manquants`,
 * servi par l'aperçu, même liste que le refus du devis automatique) n'est
 * JAMAIS posé par « Auto-remplir ». Seul un rôle sans AUCUNE ligne dans
 * `kit.inclus` refuse (un article « prix à renseigner » reste une ligne
 * visible, AGR130). La cause est celle que le serveur sert : pour un variateur
 * absent, `variateur.motif` (ex. « kW de plaque à relever … »).
 * Rend le message FR, ou `null` quand rien ne s'oppose.
 */
export function refusAutoRemplirPompage(donnees) {
  const d = donnees || {}
  const lignes = Array.isArray(d.kit?.inclus) ? d.kit.inclus : []
  const absents = (Array.isArray(d.roles_minimum_manquants) ? d.roles_minimum_manquants : [])
    .filter((r) => r && r.cle && !lignes.some((l) => l?.cle === r.cle))
  if (!absents.length) return null
  const causes = absents.map((r) => {
    const cause = r.cle === 'variateur' && d.variateur?.motif ? d.variateur.motif : r.motif
    return `${r.libelle || r.cle}${cause ? ` : ${cause}` : ''}`
  })
  return `Auto-remplir indisponible — kit incomplet (${causes.join(' ; ')}).`
}

/** AGQ26 (C-AGQ-025) — le site du lead pour l'aperçu : ville de calcul + GPS, jamais inventés. */
export function siteDuLead(villeCalcul, lead) {
  return { ville: villeCalcul || '', lat: lead?.gps_lat ?? '', lon: lead?.gps_lng ?? '' }
}
