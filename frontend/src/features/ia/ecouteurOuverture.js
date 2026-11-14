// COP-F5 — « Demander à l'assistant » marche dès le PREMIER clic.
//
// Avant : l'écouteur de l'événement `EVENEMENT_OUVRIR` vivait dans le panneau
// Copilote, monté (chunk lazy) seulement après une première ouverture — l'événement
// émis par la fiche d'un lead partait donc dans le vide au premier usage. Cet
// écouteur-ci est installé au démarrage (par `module.config.jsx`, chargé avec
// l'application) : tant que le panneau n'est pas monté, il garde la demande en
// attente et ouvre le tiroir ; le panneau la reprend à son montage. Une fois
// monté, le panneau écoute lui-même (pas de double traitement).
import { EVENEMENT_OUVRIR } from './copilotMessages.js'
import { openCopilot } from './store/iaSlice.js'

let panneauMonte = false
let enAttente = null
let installe = false
let ecouteur = null

export function signalerPanneauMonte(monte) {
  panneauMonte = monte
}

/** La demande reçue avant le montage du panneau (une seule fois), ou `null`. */
export function prendreEnAttente() {
  const detail = enAttente
  enAttente = null
  return detail
}

// `chargerStore` est injectable (tests) ; le store est importé À LA DEMANDE pour
// ne pas l'instancier au chargement du registre des modules.
export function installerEcouteurOuverture(chargerStore = () => import('../../store/index.js')) {
  if (installe || typeof window === 'undefined') return
  installe = true
  ecouteur = (e) => {
    if (panneauMonte) return
    enAttente = e?.detail || {}
    chargerStore()
      .then(({ store }) => store.dispatch(openCopilot()))
      .catch(() => { enAttente = null })
  }
  window.addEventListener(EVENEMENT_OUVRIR, ecouteur)
}

/** Pour les tests : retire l'état partagé. */
export function reinitialiserEcouteurOuverture() {
  if (ecouteur && typeof window !== 'undefined') window.removeEventListener(EVENEMENT_OUVRIR, ecouteur)
  ecouteur = null
  panneauMonte = false
  enAttente = null
  installe = false
}
