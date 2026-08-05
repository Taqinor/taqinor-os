// NTADM19 — écran « Quoi de neuf » : contenu de l'onglet « Annonces » de la
// cloche. Liste les annonces PRODUIT de l'éditeur (NTADM18) avec un rendu
// markdown simple et un marquage « lu ».
//
// Le markdown est rendu en ÉLÉMENTS REACT, jamais via `dangerouslySetInnerHTML`
// : le corps d'une annonce est du texte saisi côté éditeur, et le passer en
// HTML brut ouvrirait une injection dans la coquille de TOUS les tenants. Le
// sous-ensemble supporté est volontairement minuscule (titres `##`, listes
// `-`, gras `**…**`, paragraphes) — « corps markdown COURT » (NTADM18).
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

export default function AnnoncesTab({ annonces = [], onMarquerLu }) {
  if (annonces.length === 0) {
    return (
      <div className="nb-empty" data-testid="annonces-vide">
        Aucune nouveauté pour le moment.
      </div>
    )
  }

  return (
    <div className="nb-group" data-testid="annonces-liste">
      {annonces.map((a) => (
        <div
          key={a.id}
          className={`nb-annonce${a.lu ? '' : ' nb-annonce-non-lue'}`}
          data-testid={`annonce-${a.id}`}
          data-lu={a.lu ? '1' : '0'}
        >
          <div className="nb-annonce-entete">
            <strong>{a.titre}</strong>
            {!a.lu && (
              <span className="nb-tab-count" aria-label="Non lue">Nouveau</span>
            )}
          </div>
          <div className="nb-annonce-corps">
            {renderMarkdownSimple(a.corps)}
          </div>
          {!a.lu && (
            <button
              type="button"
              className="nb-link-btn"
              onClick={() => onMarquerLu?.(a.id)}
              aria-label={`Marquer « ${a.titre} » comme lue`}
            >
              Marquer comme lu
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
