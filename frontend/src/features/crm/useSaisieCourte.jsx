// AERR117 — la saisie courte (un nom, un motif) par une boîte MAISON, à la place
// de `window.prompt` (natif, non thémé, bloquant). Même forme que `useRaisonFroid` :
// une promesse qui rend le texte saisi (trimé), ou `null` si l'utilisateur annule.
import { useCallback, useRef, useState } from 'react'
import { Button, Input } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'

// eslint-disable-next-line react-refresh/only-export-components -- hook co-localisé avec sa boîte (dev HMR only) (D-ENF22)
function SaisieCourteDialog({ titre, label, onFin }) {
  const [texte, setTexte] = useState('')
  const valider = () => { if (texte.trim()) onFin(texte.trim()) }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onFin(null) }} className="sm:max-w-md" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">{titre}</h3>
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); valider() }}
        noValidate
      >
        <div className="modal-body">
          <label className="form-label" htmlFor="saisie-courte">{label}</label>
          <Input id="saisie-courte" value={texte} autoFocus autoComplete="off"
                 onChange={(e) => setTexte(e.target.value)} />
        </div>
        <div className="modal-footer">
          <Button type="button" variant="outline" onClick={() => onFin(null)}>Annuler</Button>
          <Button type="submit" disabled={!texte.trim()}>Valider</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}

export function useSaisieCourte() {
  const [demande, setDemande] = useState(null)
  const fin = useRef(null)
  const demanderSaisie = useCallback((titre, label = titre) => new Promise((resolve) => {
    fin.current = resolve
    setDemande({ titre, label })
  }), [])
  const finir = useCallback((valeur) => {
    setDemande(null)
    fin.current?.(valeur)
    fin.current = null
  }, [])
  return {
    demanderSaisie,
    dialogueSaisie: demande ? <SaisieCourteDialog {...demande} onFin={finir} /> : null,
  }
}

export default useSaisieCourte
