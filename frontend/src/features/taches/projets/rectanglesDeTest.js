/* Aide de TEST (jamais importée par un écran) : dnd-kit mesure les rectangles et jsdom n'en a pas. On pose des colonnes
   de Tableau côte à côte — une colonne = 280 px de large tous les 300 px, une carte 264 × 60 dedans — et on rend la
   fonction qui remet la mesure d'origine. Partagée par `VueChronologie.test.jsx` et `pages/taches/Projet.test.jsx`. */
export function poserRectangles() {
  const original = Element.prototype.getBoundingClientRect
  Element.prototype.getBoundingClientRect = function rect() {
    const colonne = this.matches?.('section.ep-col') ? this : this.closest?.('section.ep-col')
    if (!colonne) return original.call(this)
    const rang = Array.from(colonne.parentElement.children).indexOf(colonne)
    const carte = this.classList?.contains('ep-carte')
    const gauche = rang * 300 + (carte ? 8 : 0)
    const largeur = carte ? 264 : 280
    // R2-063 : les cartes d'une colonne se suivent (70 px chacune) — sans cela elles se superposeraient toutes
    const rangCarte = carte ? Array.from(colonne.querySelectorAll('.ep-carte')).indexOf(this) : 0
    const haut = carte ? 40 + rangCarte * 70 : 0
    const hauteur = carte ? 60 : 400
    return { x: gauche, y: haut, left: gauche, top: haut, right: gauche + largeur, bottom: haut + hauteur, width: largeur, height: hauteur, toJSON() { return this } }
  }
  return () => { Element.prototype.getBoundingClientRect = original }
}
