// NTUX10 — Quick-create universel depuis la palette de commandes. Module PUR
// (aucun import React, testable côté node:test) : un événement `window`
// (même patron que `taqinor:command-palette` déjà utilisé par le bouton ⌘K
// du Header, providers/CommandPalette.jsx) découple le déclencheur (la
// palette) de l'hôte qui rend réellement le modal
// (`QuickCreateModalHost.jsx`, monté une fois près de la racine) — la
// palette peut se fermer sans démonter le modal qu'elle vient d'ouvrir.
export const QUICK_CREATE_EVENT = 'taqinor:quick-create'

// Registre des types quick-create qui ouvrent un MODAL (par-dessus l'écran
// courant, sans navigation). « Devis » n'y figure PAS : DevisGenerator est
// déjà un écran de création dédié (cf. providers/shortcuts.js) — le sélecteur
// « Créer un devis » de la palette continue de NAVIGUER, comme avant.
export const QUICK_CREATE_TYPES = [
  { id: 'lead', label: 'Créer un lead' },
  { id: 'client', label: 'Créer un client' },
  { id: 'ticket', label: 'Créer un ticket SAV' },
  { id: 'produit', label: 'Créer un produit' },
]

export function isQuickCreateType(id) {
  return QUICK_CREATE_TYPES.some((t) => t.id === id)
}

/** filterQuickCreateTypes — même filtre que `filterCreateActions`
 *  (providers/commandActions.js) : requête vide → tous, sinon sous-chaîne du
 *  libellé (insensible à la casse). */
export function filterQuickCreateTypes(query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return QUICK_CREATE_TYPES
  return QUICK_CREATE_TYPES.filter((t) => t.label.toLowerCase().includes(q))
}

/** openQuickCreate(type) — émet l'événement window ; no-op hors navigateur
 *  (SSR/tests sans DOM). */
export function openQuickCreate(type) {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  window.dispatchEvent(new CustomEvent(QUICK_CREATE_EVENT, { detail: { type } }))
}
