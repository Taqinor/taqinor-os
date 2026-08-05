// NTADM19 — écran « Quoi de neuf » : contenu de l'onglet « Annonces » de la
// cloche. Liste les annonces PRODUIT de l'éditeur (NTADM18) avec un rendu
// markdown simple et un marquage « lu ».
// Rendu markdown : voir `src/lib/markdownSimple.jsx` (jamais de HTML brut).
import { renderMarkdownSimple } from '../../lib/markdownSimple'

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
