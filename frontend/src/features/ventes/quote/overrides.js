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
// QJR214 — `cheminsRefuses` est désormais IMPORTÉ par `frontend/src/api/
// ventesApi.js` (client HTTP du registre, `poserOverrides`) pour refuser un
// chemin hors liste blanche CÔTÉ ÉCRAN, avant tout appel réseau — la même
// liste blanche, jamais une seconde copie. Le reste du module (sérialisation
// depuis le reducer QJR87) reste AJOUTÉ TESTÉ, câblé à l'écran par QJR215.
import { DRAPEAUX_TOUCHE, ETAT_INITIAL } from './sizingReducer.js'

/**
 * Liste blanche du contrat QJR1, RECOPIÉE À L'IDENTIQUE (ordre compris).
 * Aucun chemin ajouté ni retiré : le test échoue si le contrat bouge.
 */
export const CHEMINS_AUTORISES = Object.freeze([
  'taille.nb_panneaux', 'taille.panel_watt', 'taille.kwc',
  'taille.batterie_nb_modules', 'taille.batterie_module_kwh',
  'scenario', 'recommended_option',
  'profil.occupation', 'profil.factures_mensuelles_reelles', 'profil.conso_annuelle',
  'profil.equipements.<clef>',
  'tarif.distributeur', 'tarif.tranches', 'tarif.charges_fixes_mad',
  'etude.jour_reference',
  'mode_installation', 'structure', 'tension', 'pompe_alim',
])

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
export const CHEMIN_PAR_DRAPEAU = Object.freeze({
  mode: { chemin: 'mode_installation', champ: 'modeInstallation' },
  structure: { chemin: 'structure', champ: 'structure' },
  tension: { chemin: 'tension', champ: 'tension' },
  pompeAlim: { chemin: 'pompe_alim', champ: 'pompeAlim' },
  nbPanneaux: { chemin: 'taille.nb_panneaux', champ: 'nbPanneaux', nombre: true },
  scenario: { chemin: 'scenario', champ: 'scenario' },
})

const MOTIF_EQUIPEMENT = /^profil\.equipements\.[^.]+$/

/**
 * Un chemin est-il dans la liste blanche ? `profil.equipements.<clef>` est le
 * SEUL motif dynamique du contrat (`<clef>` = un nom d'équipement réel, jamais
 * un index de position).
 */
export function cheminAutorise(chemin) {
  if (typeof chemin !== 'string' || chemin === '') return false
  if (chemin === 'profil.equipements.<clef>') return false // le motif, pas un chemin
  if (CHEMINS_AUTORISES.includes(chemin)) return true
  return MOTIF_EQUIPEMENT.test(chemin)
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
    const entree = (payload || {})[def.chemin]
    if (!entree || typeof entree !== 'object' || !('valeur' in entree)) continue
    if (entree.valeur === null || entree.valeur === undefined) continue
    partiel[def.champ] = def.nombre ? String(entree.valeur) : entree.valeur
    touche[drapeau] = true
  }
  return Object.keys(touche).length ? { ...partiel, touche } : {}
}

/**
 * PATCH = FUSION (`notes.fusion` du contrat). Le sous-ensemble reçu est fondu
 * dans le registre existant — jamais un remplacement intégral. Un chemin
 * refusé par la liste blanche lève : la surface est FERMÉE, pas de `**kwargs`
 * silencieux.
 */
export function fusionner(registre, patch) {
  const refuses = cheminsRefuses(patch)
  if (refuses.length) {
    throw new TypeError('overrides.js : chemin(s) hors liste blanche du contrat '
      + `QJR1 — ${refuses.join(', ')} (refusé en 400 côté serveur).`)
  }
  return { ...(registre || {}), ...(patch || {}) }
}
