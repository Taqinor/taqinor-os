import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

/* TCH43 — point de montage de la feuille de saisie, VIDE à dessein : la coquille l'ouvre
   (bouton « Ajouter », touche `c t`, événement `taqinor:taches:saisir`), TCH82 y construit
   ChampSaisie, les puces, l'aperçu d'une liste collée. En attendant : une feuille nommée,
   fermable au clavier (Échap), qui rend le focus à celui qui l'a ouverte. */
export default function FeuilleSaisie({ ouverte, onFermer }) {
  const fermer = useRef(null)
  const origine = useRef(null)

  useEffect(() => {
    if (!ouverte) return undefined
    origine.current = document.activeElement
    fermer.current?.focus()
    const surTouche = (e) => { if (e.key === 'Escape') onFermer?.() }
    document.addEventListener('keydown', surTouche)
    return () => {
      document.removeEventListener('keydown', surTouche)
      origine.current?.focus?.()
    }
  }, [ouverte, onFermer])

  if (!ouverte) return null
  return (
    <>
      <div className="voile" onClick={onFermer} aria-hidden="true" />
      <div className="feuille cran-50 dialogue-bureau" role="dialog" aria-modal="true" aria-label="Ajouter une tâche">
        <div className="feuille-entete">
          <button ref={fermer} type="button" className="bouton-icone" aria-label="Fermer" onClick={onFermer}>
            <X className="i" aria-hidden="true" />
          </button>
          <div className="feuille-titre">Ajouter une tâche</div>
          <span />
        </div>
      </div>
    </>
  )
}
