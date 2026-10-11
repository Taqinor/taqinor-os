// ENF22 — helpers extraits de RaccourcisAtelier.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/**
 * CAL101 — la table UNIQUE des raccourcis.
 * `action` est la clé du gestionnaire attendu dans la prop `actions` ;
 * `touche` est comparée à `event.key` SANS casse ; `ctrl` exige la touche
 * Contrôle (ou Commande) ; `libelle` est ce que l'aide affiche.
 */
export const RACCOURCIS = [
  { action: 'outilTrace', touche: 't', libelle: 'Outil tracé de toit', affichage: 'T' },
  { action: 'outilObstacle', touche: 'o', libelle: 'Outil obstacle', affichage: 'O' },
  { action: 'outilZone', touche: 'z', libelle: 'Outil zone', affichage: 'Z' },
  { action: 'outilMesure', touche: 'm', libelle: 'Outil mesure', affichage: 'M' },
  { action: 'aimantation', touche: 'a', libelle: 'Activer ou couper l’aimantation', affichage: 'A' },
  { action: 'supprimer', touche: 'delete', libelle: 'Supprimer la sélection', affichage: 'Suppr' },
  { action: 'dupliquer', touche: 'd', ctrl: true, libelle: 'Dupliquer la sélection', affichage: 'Ctrl + D' },
  { action: 'pleinEcran', touche: 'f', libelle: 'Plein écran', affichage: 'F' },
]

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
