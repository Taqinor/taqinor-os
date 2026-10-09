// EDC5 — LA DÉCISION CLAVIER DU FORMULAIRE DEVIS (module PUR).
// ---------------------------------------------------------------------------
// Fondateur 09/10/2026 : « l'édition complète est glitchy et revient d'un coup
// au devis ». Cause n° 1 prouvée : `<form onSubmit>` sans garde — la soumission
// IMPLICITE du navigateur (WHATWG 4.10.22.2 : Entrée dans un champ clique le
// premier bouton submit du formulaire) enregistrait le devis et quittait
// l'éditeur à la moindre Entrée dans Qté, Prix, une facture, la remise…
//
// Règle (patron Odoo 17 `list_renderer`) : Entrée n'enregistre JAMAIS ; dans
// une cellule de la table des lignes, Entrée passe au MÊME champ de la ligne
// suivante (ou ajoute une ligne sur la dernière) ; Ctrl/Cmd+S et
// Ctrl/Cmd+Entrée enregistrent (par `requestSubmit()`, donc la même validation
// qu'un clic).
//
// `decisionTouche(e, racine)` ne touche à RIEN : elle lit un événement (ou un
// objet de même forme) et rend l'une des cinq décisions ; l'appelant
// (`DevisGenerator.jsx`) applique. Les deux aides DOM (`ligneSuivante`,
// `champCorrespondant`) ne lisent que `closest`/`matches`/`querySelector(All)`/
// `children`/`nextElementSibling` — testables hors navigateur (node:test).

/** Les cinq décisions possibles. */
export const DECISIONS = Object.freeze(['ignorer', 'bloquer', 'ligne-suivante', 'ajouter-ligne', 'enregistrer'])

// Entrée sur ces champs = leur PROPRE activation (cliquer, choisir un
// fichier) : jamais interceptée. Une case à cocher n'en fait pas partie :
// Entrée n'y coche rien (c'est Espace) mais y déclenche la soumission
// implicite — elle est donc bloquée comme un champ texte.
const TYPES_ACTIVABLES = new Set(['submit', 'button', 'reset', 'image', 'file'])
// Listes déroulantes et popovers : Entrée y CHOISIT (ProduitPicker, Combobox).
const SELECTEUR_POPUP = '[role="combobox"], [role="listbox"], [data-radix-popper-content-wrapper]'
const SELECTEUR_DIALOGUE = '[role="dialog"], [role="alertdialog"]'
const SELECTEUR_LIGNE = 'tr[data-line-key]'
/** Champs focalisables d'une cellule de ligne (désactivés exclus). */
export const SELECTEUR_CHAMP = 'input:not([disabled]):not([type="hidden"]), '
  + 'select:not([disabled]), textarea:not([disabled]), button:not([disabled])'

const contient = (racine, noeud) => !racine || typeof racine.contains !== 'function'
  || racine.contains(noeud)

/**
 * Décide quoi faire d'une touche pressée dans le formulaire du devis.
 *
 * @param {KeyboardEvent|object} e  `key`, `ctrlKey`, `metaKey`, `shiftKey`,
 *        `altKey`, `repeat`, `isComposing`, `defaultPrevented`, `target`
 * @param {Element} [racine]        Le `<form>` (par défaut `e.currentTarget`)
 * @returns {'ignorer'|'bloquer'|'ligne-suivante'|'ajouter-ligne'|'enregistrer'}
 */
export function decisionTouche(e, racine = e?.currentTarget ?? null) {
  if (!e || e.defaultPrevented) return 'ignorer'
  // Saisie IME en cours (accents composés, clavier arabe…) : Entrée valide la
  // composition, jamais le formulaire.
  // (l'événement synthétique React ne porte pas `isComposing` : lire le natif.)
  if (e.isComposing || e.nativeEvent?.isComposing || e.keyCode === 229) return 'ignorer'
  const cible = e.target
  if (!cible || typeof cible.closest !== 'function') return 'ignorer'
  // Événement remonté par un PORTAIL React (popover, dialogue porté hors du
  // formulaire) : sa cible n'est pas dans le formulaire — pas notre affaire.
  if (!contient(racine, cible)) return 'ignorer'
  // Dialogue imbriqué DANS le formulaire : ses touches lui appartiennent.
  // (Le panneau Sheet qui CONTIENT le formulaire n'est pas « imbriqué ».)
  const dialogue = cible.closest(SELECTEUR_DIALOGUE)
  if (dialogue && racine && dialogue !== racine && contient(racine, dialogue)) return 'ignorer'

  const modificateur = Boolean(e.ctrlKey || e.metaKey)
  const toucheS = e.key === 's' || e.key === 'S'
  if (modificateur && !e.altKey && (toucheS || e.key === 'Enter')) {
    // Touche maintenue : un seul enregistrement, les répétitions sont avalées.
    return e.repeat ? 'bloquer' : 'enregistrer'
  }
  if (e.key !== 'Enter') return 'ignorer'

  const balise = String(cible.tagName || '').toUpperCase()
  // <textarea> : Entrée = retour à la ligne ; <button> / <select> : leur
  // activation propre ; aucun ne provoque de soumission implicite.
  if (balise !== 'INPUT') return 'ignorer'
  const type = String(cible.type || 'text').toLowerCase()
  if (TYPES_ACTIVABLES.has(type)) return 'ignorer'
  if (cible.closest(SELECTEUR_POPUP)) return 'ignorer'

  const ligne = cible.closest(SELECTEUR_LIGNE)
  // Hors table des lignes (ou Maj+Entrée) : on bloque, rien de plus.
  if (!ligne || e.shiftKey || e.altKey) return 'bloquer'
  return ligneSuivante(ligne) ? 'ligne-suivante' : 'ajouter-ligne'
}

/** La ligne de devis suivante (`tr[data-line-key]`), ou null sur la dernière. */
export function ligneSuivante(ligne) {
  let n = ligne?.nextElementSibling ?? null
  while (n && !(typeof n.matches === 'function' && n.matches(SELECTEUR_LIGNE))) {
    n = n.nextElementSibling
  }
  return n
}

/**
 * Le MÊME champ que `cible`, dans les lignes qui suivent la sienne : même
 * cellule (par `data-label`, sinon par rang de cellule) et même rang de champ
 * dans la cellule (ex. TVA puis base légale). Une ligne de section/note n'a pas
 * la cellule « Qté » : elle est sautée. Repli : premier champ de la ligne
 * suivante. null s'il n'y a pas de ligne suivante.
 */
export function champCorrespondant(cible) {
  const ligne = cible?.closest?.(SELECTEUR_LIGNE)
  const cellule = cible?.closest?.('td')
  const suivante = ligneSuivante(ligne)
  if (!ligne || !cellule || !suivante) return null
  const libelle = typeof cellule.getAttribute === 'function'
    ? cellule.getAttribute('data-label') : null
  const rangCellule = Array.prototype.indexOf.call(ligne.children, cellule)
  const rangChamp = Math.max(0,
    Array.prototype.indexOf.call(cellule.querySelectorAll(SELECTEUR_CHAMP), cible))
  for (let l = suivante; l; l = ligneSuivante(l)) {
    const c = libelle
      ? Array.prototype.find.call(l.children, (td) => td.getAttribute?.('data-label') === libelle)
      : l.children[rangCellule]
    const champs = c ? c.querySelectorAll(SELECTEUR_CHAMP) : []
    if (champs.length) return champs[rangChamp] ?? champs[0]
  }
  return suivante.querySelector(SELECTEUR_CHAMP)
}
