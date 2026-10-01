// QJR88 — LE REGISTRE ÉNUMÉRABLE DES SURCHARGES, CÔTÉ ÉCRAN (module PUR).
// ---------------------------------------------------------------------------
// Aligné sur le contrat QJR1 —
// `backend/django_core/apps/ventes/contract_samples/devis_overrides.json`
// (`GET/PATCH /api/django/ventes/devis/<pk>/overrides/`) : les chemins ci-dessous
// sont RECOPIÉS À L'IDENTIQUE de sa liste blanche `notes.chemins_autorises`
// (décision fondateur D12 du 29/08), et `overrides.test.mjs` LIT le contrat sur
// disque pour prouver l'égalité — ce n'est donc pas un jeu de noms local qui
// pourrait dériver (R4-A.5 : le mécanisme `saisie_manuelle` noms-seuls est retiré).
//
// POURQUOI. Aujourd'hui RIEN n'énumère l'ensemble « touché » : c'est la cause
// mécanique du prix tapé qui revient à `false` et de la taxe « tout nouveau
// champ auto-rempli doit inventer son propre drapeau ». Les six drapeaux sont
// devenus de l'ÉTAT en QJR87 ; ici ils deviennent des CHEMINS adressables.
//
// SÉMANTIQUE DE PATCH = FUSION, JAMAIS REMPLACEMENT (`notes.fusion` du
// contrat) : envoyer `{"taille.nb_panneaux": …}` ne touche AUCUN autre chemin
// déjà posé.
//
// QJR214 — `cheminsRefuses` est IMPORTÉ par `frontend/src/api/ventesApi.js`
// (client HTTP du registre, `poserOverrides`) pour refuser un chemin hors
// liste blanche CÔTÉ ÉCRAN, avant tout appel réseau — la même liste blanche,
// jamais une seconde copie.
//
// QJR572 — CE QUI EST CÂBLÉ À L'ÉCRAN : `valeursImposees` (ce que le registre
// impose, pour aligner Scénario / Option recommandée / nombre de panneaux à
// l'arrivée du registre) et `ecartsAuRegistre` (le patch / les retours à
// l'automatique envoyés à l'enregistrement d'une édition). `serialiser` /
// `hydrater` (pont QJR88) restent testés mais NE SONT PAS branchés : ils
// poseraient une surcharge pour tout champ touché, y compris les chemins
// que le moteur ne lit pas. La fusion d'un PATCH est faite par le SERVEUR.
import { DRAPEAUX_TOUCHE, ETAT_INITIAL } from './sizingReducer.js'

/**
 * Liste blanche du contrat QJR1, RECOPIÉE À L'IDENTIQUE (ordre compris) — la
 * D12 réduite par D-QJR5-8 (QJR573) aux chemins que le moteur LIT. Le test
 * échoue si le contrat bouge.
 */
export const CHEMINS_AUTORISES = Object.freeze([
  'taille.nb_panneaux', 'taille.panel_watt', 'taille.kwc',
  'scenario', 'recommended_option',
  'etude.jour_reference',
])

/**
 * QJR571 (D-QJR5-8) — les chemins de la liste blanche que le MOTEUR NE LIT
 * PAS, RECOPIÉS À L'IDENTIQUE de `notes.chemins_non_lus` du contrat (le test
 * l'épingle). QJR573 l'a ramenée à [] : chaque chemin non lu a été retiré de la
 * liste blanche. Une surcharge retirée déjà posée en base arrive du serveur
 * avec `non_lu: true` (lecture seule) ; l'écran le dit au vendeur.
 */
export const CHEMINS_NON_LUS = Object.freeze([])

/** Le chemin est-il non lu par le moteur ? */
export function cheminNonLu(chemin) {
  if (typeof chemin !== 'string' || chemin === '') return false
  return CHEMINS_NON_LUS.includes(chemin)
}

/** Les trois origines du contrat (`notes.origine_valeurs`) — jamais une 4e. */
export const ORIGINES = Object.freeze(['manuel', 'import', 'api'])

/**
 * Drapeau « touché » du reducer QJR87 → chemin du registre, ET champ d'état
 * porteur de la valeur. C'est CETTE table que le test d'exhaustivité vérifie :
 * un drapeau ajouté au reducer sans son chemin ici rend le test ROUGE.
 *
 * Le registre contient légitimement PLUS de chemins que l'écran n'a de
 * drapeaux (import OCR, tarif, profil…) — l'exhaustivité va des drapeaux vers
 * les chemins, jamais l'inverse.
 *
 * `taille.kwc` / `taille.panel_watt` ne sont volontairement PAS émis depuis
 * l'écran : à l'écran le kWc cible est DÉRIVÉ du compte de panneaux (et
 * inversement, `sizingReducer.SAISI`), et le contrat n'accepte que des
 * ENTRÉES — poser les deux créerait un second endroit où ce nombre pourrait
 * diverger (`notes.entrees_seules`).
 */
//
// QJR573 (D-QJR5-8) — `mode`, `structure`, `tension` et `pompeAlim` n'ont PLUS
// de chemin (`chemin: null`) : ces choix sont portés par la colonne du devis
// (marché) ou par les LIGNES composées, et le registre les refuse en 400. Le
// drapeau reste DÉCLARÉ ici (l'exhaustivité tient), `serialiser` ne l'émet pas.
export const CHEMIN_PAR_DRAPEAU = Object.freeze({
  mode: { chemin: null, champ: 'modeInstallation' },
  structure: { chemin: null, champ: 'structure' },
  tension: { chemin: null, champ: 'tension' },
  pompeAlim: { chemin: null, champ: 'pompeAlim' },
  nbPanneaux: { chemin: 'taille.nb_panneaux', champ: 'nbPanneaux', nombre: true },
  scenario: { chemin: 'scenario', champ: 'scenario' },
})

/**
 * Un chemin est-il dans la liste blanche ? QJR573 — liste FERMÉE, sans motif
 * dynamique (`profil.equipements.<clef>` est retiré).
 */
export function cheminAutorise(chemin) {
  if (typeof chemin !== 'string' || chemin === '') return false
  return CHEMINS_AUTORISES.includes(chemin)
}

/** Chemins d'un payload que le serveur refuserait en 400 (liste, vide = OK). */
export const cheminsRefuses = (payload) =>
  Object.keys(payload || {}).filter((c) => !cheminAutorise(c))

/**
 * ÉTAT DU REDUCER → PAYLOAD D'OVERRIDES. N'émet QUE les chemins dont le
 * drapeau « touché » est posé : un PATCH ne parle que de ce que le vendeur a
 * réellement fixé (le reste reste en mode automatique, `effectif` = `auto`).
 *
 * `meta` porte l'audit du contrat : `{ pose_le, pose_par, origine }`
 * (`origine` par défaut `manuel`). Les clés d'audit absentes sont OMISES —
 * jamais inventées.
 */
export function serialiser(etat, meta = {}) {
  const source = etat || ETAT_INITIAL
  const touche = source.touche || {}
  const origine = meta.origine ?? 'manuel'
  if (!ORIGINES.includes(origine)) {
    throw new TypeError(`overrides.js : origine « ${origine} » hors contrat `
      + `(${ORIGINES.join(', ')}).`)
  }
  const payload = {}
  // Union des drapeaux CONNUS et de ceux réellement portés par l'état : un
  // drapeau ajouté au reducer sans son chemin ici LÈVE (au lieu d'être oublié
  // en silence — c'est la moitié exécutable du test d'exhaustivité).
  const drapeaux = [...new Set([...DRAPEAUX_TOUCHE, ...Object.keys(touche)])]
  for (const drapeau of drapeaux) {
    if (!touche[drapeau]) continue
    const def = CHEMIN_PAR_DRAPEAU[drapeau]
    if (!def) {
      throw new Error(`overrides.js : le drapeau « ${drapeau} » n'a AUCUN chemin `
        + 'dans le registre — ajoutez-le à CHEMIN_PAR_DRAPEAU (contrat QJR1).')
    }
    if (!def.chemin) continue // QJR573 — porté hors du registre
    const brut = source[def.champ]
    const valeur = def.nombre ? (Number.parseFloat(brut) || 0) : brut
    payload[def.chemin] = {
      valeur,
      ...(meta.pose_le ? { pose_le: meta.pose_le } : {}),
      ...(meta.pose_par ? { pose_par: meta.pose_par } : {}),
      origine,
    }
  }
  return payload
}

/**
 * PAYLOAD D'OVERRIDES → ÉTAT PARTIEL DU REDUCER (l'inverse de `serialiser`).
 * Un chemin présent pose SA valeur ET son drapeau « touché » : c'est un choix
 * déjà fait, il ne doit plus jamais être écrasé par un pré-remplissage.
 * Les chemins hors liste blanche et les chemins sans drapeau d'écran sont
 * IGNORÉS (jamais une écriture sauvage dans l'état).
 */
export function hydrater(payload) {
  const partiel = {}
  const touche = {}
  for (const [drapeau, def] of Object.entries(CHEMIN_PAR_DRAPEAU)) {
    if (!def.chemin) continue
    const entree = (payload || {})[def.chemin]
    if (!entree || typeof entree !== 'object' || !('valeur' in entree)) continue
    if (entree.valeur === null || entree.valeur === undefined) continue
    partiel[def.champ] = def.nombre ? String(entree.valeur) : entree.valeur
    touche[drapeau] = true
  }
  return Object.keys(touche).length ? { ...partiel, touche } : {}
}

/**
 * QJR572 — les trois chemins LUS que l'écran porte lui-même : Scénario,
 * Option recommandée, nombre de panneaux. Ce sont les SEULS que
 * `ecartsAuRegistre` peut écrire.
 */
export const CHEMINS_ECRAN = Object.freeze(['scenario', 'recommended_option', 'taille.nb_panneaux'])

/** Les options que le moteur reconnaît pour `recommended_option`. */
const RECOMMANDATIONS_LUES = Object.freeze(['Sans batterie', 'Avec batterie'])

/**
 * QJR572 — `{chemin: valeur}` des entrées que le registre IMPOSE (bloc
 * `effectif`, source ≠ 'auto'). Registre absent ou vide → `{}`.
 */
export function valeursImposees(overridesReg) {
  const effectif = overridesReg?.effectif
  const imposees = {}
  if (!effectif || typeof effectif !== 'object') return imposees
  for (const [chemin, entree] of Object.entries(effectif)) {
    if (!entree || typeof entree !== 'object') continue
    if (!entree.source || entree.source === 'auto') continue
    imposees[chemin] = entree.effectif
  }
  return imposees
}

/**
 * QJR572 — CE QUE L'ENREGISTREMENT D'UNE ÉDITION DOIT DIRE AU REGISTRE.
 *
 * `ecran` = `{scenario, recommended_option, 'taille.nb_panneaux'}` tels
 * qu'affichés (Option recommandée en valeur BRUTE du Select, « Auto »
 * compris). Seul un chemin DÉJÀ surchargé dont la valeur écran diffère
 * produit un écart :
 * - une valeur que le moteur lit → `patch[chemin] = {valeur}` ;
 * - « Auto » (ou « Aucune recommandation », que le moteur ne lit pas) →
 *   `regenerer` (DELETE `?chemin=`), `etude_params` reprend la main.
 * Un chemin non surchargé n'est JAMAIS posé : rien à la création, rien
 * sans surcharge. Un nombre de panneaux illisible n'écrit rien.
 */
export function ecartsAuRegistre(ecran, overridesReg) {
  const imposees = valeursImposees(overridesReg)
  const patch = {}
  const regenerer = []
  for (const chemin of CHEMINS_ECRAN) {
    if (!(chemin in imposees) || !ecran || !(chemin in ecran)) continue
    const valeur = ecran[chemin]
    if (chemin === 'recommended_option' && !RECOMMANDATIONS_LUES.includes(valeur)) {
      regenerer.push(chemin)
      continue
    }
    if (chemin === 'taille.nb_panneaux') {
      const n = Number.parseInt(valeur, 10)
      if (!(n > 0)) continue
      if (n !== Number(imposees[chemin])) patch[chemin] = { valeur: n }
      continue
    }
    if (valeur == null || valeur === '') continue
    if (valeur !== imposees[chemin]) patch[chemin] = { valeur }
  }
  return { patch, regenerer }
}
