// QJR89 — STRATÉGIE DE MARCHÉ : RÉSIDENTIEL (module PUR).
// ---------------------------------------------------------------------------
// Un module de marché expose UNE interface, identique pour les quatre :
//   { cle, defautScenario, champsRequis, dimensionner(etat, deps),
//     composer(etat, deps), etudePersistee(etat) }
//
// CE FICHIER N'IMPORTE QUE `valeur.js` (la primitive de la valeur signée, qui
// elle-même n'importe RIEN). C'est le point de la tâche : le chemin résidentiel
// devient **STRUCTURELLEMENT** incapable d'atteindre un producteur de
// `solar.js` — plus de `computeAutoSizing`, plus d'`estimerPanneaux`, plus
// d'`optimalKwcByPayback` à portée de main. Le SEUL dimensionneur résidentiel
// est le moteur horaire SERVEUR (U3-900, fondateur 29/08 : « ALL sizing goes
// through the new sizing tool »), et un `if` oublié ne peut plus rouvrir une
// seconde source : il n'y a plus rien à appeler ici.
//
// Module AJOUTÉ TESTÉ, IMPORTÉ PAR PERSONNE (vague M4).
import { moteur, absent, estFait } from '../valeur.js'

export const cle = 'residentiel'

/** ORDRE FONDATEUR (24/08) — deux options par défaut. */
export const defautScenario = 'Les deux (Sans + Avec)'

/**
 * Ce que le MOTEUR SERVEUR exige pour chiffrer une recommandation — les trois
 * données que son refus nomme quand elles manquent (`DevisGenerator.jsx:2671`).
 */
export const champsRequis = Object.freeze(['facture_hiver', 'ville', 'raccordement'])

/**
 * DIMENSIONNEMENT — rend `{ mode: 'serveur' }` et RIEN d'autre. Aucun chiffre,
 * aucune branche, aucun repli : l'appelant n'a pas d'autre choix que d'attendre
 * la recommandation du moteur horaire (ou d'afficher son refus FR verbatim).
 */
export function dimensionner() {
  return Object.freeze({ mode: 'serveur' })
}

/**
 * COMPOSITION — le dry-run SERVEUR (`POST /ventes/devis/composition/`, U3) est
 * la source de vérité. Ce module ne compose RIEN lui-même : il décrit le corps
 * à envoyer. Le repli local en cas de panne réseau appartient au hook
 * (`useComposition`, QJR90), qui rend la `raison` visible — jamais un repli
 * silencieux caché ici.
 */
export function composer(etat = {}) {
  return Object.freeze({
    mode: 'serveur',
    corps: Object.freeze({
      kwc: Number.parseFloat(etat.kwc) || 0,
      panel_watt: Number.parseFloat(etat.panelW) || 710,
      structure_type: etat.structure ?? 'acier',
      scenario: etat.scenario ?? defautScenario,
    }),
  })
}

/**
 * ÉTUDE PERSISTÉE — uniquement l'étude SERVEUR (moteur horaire). Tant qu'elle
 * n'est pas arrivée, `absent(motif)` : jamais un miroir JS déguisé en mesure.
 * `etat.etudeServeur` est une VALEUR SIGNÉE (QJR86) : seule une valeur de
 * source `moteur` est publiable.
 */
export function etudePersistee(etat = {}) {
  const v = etat.etudeServeur
  if (!estFait(v) || v.source !== 'moteur') {
    return absent("aucune étude serveur : le moteur horaire n'a pas encore chiffré ce devis")
  }
  return moteur(v.valeur)
}

export default { cle, defautScenario, champsRequis, dimensionner, composer, etudePersistee }
