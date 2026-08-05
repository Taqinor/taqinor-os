// NTADM19 — rendu markdown SIMPLE (sous-ensemble ferme) en elements React,
// jamais via `dangerouslySetInnerHTML` : le corps d'une annonce est du texte
// saisi cote editeur, et le passer en HTML brut ouvrirait une injection dans
// la coquille de TOUS les tenants. Sous-ensemble volontairement minuscule
// (titres `##`, listes `-`, gras `**…**`, paragraphes). Fichier separe du
// composant AnnoncesTab pour rester compatible react-refresh (un fichier
// composant n'exporte que des composants).
import { Fragment } from 'react'

/** Découpe une ligne sur `**gras**` et renvoie des nœuds React. */
function rendreGras(ligne, cle) {
  const morceaux = String(ligne).split(/\*\*(.+?)\*\*/g)
  return morceaux.map((morceau, i) => (
    // Les index impairs sont les captures du groupe = le texte en gras.
    i % 2 === 1
      ? <strong key={`${cle}-g${i}`}>{morceau}</strong>
      : <Fragment key={`${cle}-t${i}`}>{morceau}</Fragment>
  ))
}

/**
 * Rendu markdown SIMPLE (sous-ensemble fermé) en éléments React.
 * Exporté séparément pour être testable seul.
 */
export function renderMarkdownSimple(texte) {
  const lignes = String(texte || '').split('\n')
  const noeuds = []
  let listeCourante = []

  const viderListe = (cle) => {
    if (listeCourante.length === 0) return
    noeuds.push(
      <ul key={`ul-${cle}`} className="nb-annonce-liste">
        {listeCourante.map((item, i) => (
          <li key={`li-${cle}-${i}`}>{rendreGras(item, `li-${cle}-${i}`)}</li>
        ))}
      </ul>,
    )
    listeCourante = []
  }

  lignes.forEach((ligne, index) => {
    const brut = ligne.trim()
    if (brut.startsWith('- ')) {
      listeCourante.push(brut.slice(2))
      return
    }
    viderListe(index)
    if (!brut) return
    if (brut.startsWith('## ')) {
      noeuds.push(
        <h4 key={`h-${index}`} className="nb-annonce-titre">
          {rendreGras(brut.slice(3), `h-${index}`)}
        </h4>,
      )
      return
    }
    noeuds.push(
      <p key={`p-${index}`} className="nb-annonce-para">
        {rendreGras(brut, `p-${index}`)}
      </p>,
    )
  })
  viderListe('fin')
  return noeuds
}
