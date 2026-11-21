// ENF22 — helpers extraits de RaccourcisAtelier.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

import { lignesDePortee } from '@roofpro/raccourcisAtelier'

/**
 * CAL101 — la table UNIQUE des raccourcis.
 * `action` est la clé du gestionnaire attendu dans la prop `actions` ;
 * `touche` est comparée à `event.key` SANS casse ; `ctrl` exige la touche
 * Contrôle (ou Commande) ; `libelle` est ce que l'aide affiche.
 */
// ACAL414 — lue dans la table unique `@roofpro/raccourcisAtelier` (portée « atelier »).
export const RACCOURCIS = lignesDePortee('atelier').map((l) => ({
  action: l.action,
  touche: l.touches[0],
  ...(l.modificateurs?.ctrl ? { ctrl: true } : {}),
  libelle: l.libelle,
  affichage: l.ecriture,
}))

/**
 * CAL101 — vrai quand la frappe appartient à un champ de saisie. Un raccourci
 * qui volerait cette frappe rendrait les formulaires inutilisables : c'est la
 * garde la plus importante de ce fichier.
 */
export function estSaisieEnCours(cible) {
  if (!cible) return false
  const balise = (cible.tagName || '').toLowerCase()
  if (balise === 'input' || balise === 'textarea' || balise === 'select') return true
  if (cible.isContentEditable) return true
  // `contenteditable` posé en attribut (jsdom ne calcule pas toujours
  // `isContentEditable`) : on lit l'attribut lui-même.
  const attribut = typeof cible.getAttribute === 'function'
    ? cible.getAttribute('contenteditable') : null
  return attribut === '' || attribut === 'true'
}

/** Le raccourci que cette frappe désigne, ou `null`. */
export function raccourciDe(evenement) {
  const touche = String(evenement.key || '').toLowerCase()
  const avecCtrl = Boolean(evenement.ctrlKey || evenement.metaKey)
  return RACCOURCIS.find((r) => r.touche === touche
    && Boolean(r.ctrl) === avecCtrl) ?? null
}
