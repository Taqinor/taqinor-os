// Bus de la fête « affaire signée » — l'appelant (SigneDialog dans la fenêtre
// lead, DevisList…) ANNONCE la victoire ; un SEUL hôte global
// (<DealSignedCelebrationHost/>, monté dans ShellGlobal, hors de tout dialogue)
// l'affiche. Ainsi la fête n'est jamais coincée derrière une modale Radix
// (z-index, transform, pointer-events:none du body, focus-trap).
// Les chiffres (référence, TTC, kWc) sont ceux transmis par l'appelant : réels.
import { useSyncExternalStore } from 'react'

let current = null
const listeners = new Set()

function emit() { listeners.forEach((l) => l()) }

export function annoncerAffaireSignee({ reference, montantTtc, kwc = null }) {
  current = { reference, montantTtc, kwc }
  emit()
}

export function effacerAffaireSignee() {
  if (current === null) return
  current = null
  emit()
}

function subscribe(listener) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

const getSnapshot = () => current

export function useAffaireSignee() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
