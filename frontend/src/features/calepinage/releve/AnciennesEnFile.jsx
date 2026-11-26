import { useCallback, useEffect, useState } from 'react'
import { adopterAnciennes, anciennesEnFile, supprimerAnciennes } from '../fileEnvoiPhotos'

/* Revue ACAL1949 (point 3) — ce qui a été gardé sur cet appareil AVANT la règle « une entrée = son utilisateur » (aucun
   utilisateur noté) n'est ni envoyé seul ni jeté en silence : l'utilisateur connecté le voit ici et choisit. Rien n'est
   montré tant que la session n'est pas connue. `onApres()` : relancer le rejeu ordinaire (après « Envoyer »). */
export default function AnciennesEnFile({ calepinageId, onApres }) {
  const [anciennes, setAnciennes] = useState({ releve: false })
  const [enCours, setEnCours] = useState(false)
  const relire = useCallback(
    () => Promise.resolve(anciennesEnFile(calepinageId)).then((a) => setAnciennes(a ?? { releve: false })).catch(() => {}),
    [calepinageId],
  )
  useEffect(() => { if (calepinageId) relire() }, [calepinageId, relire])

  if (!anciennes.releve) return null
  const agir = async (geste) => {
    setEnCours(true)
    try {
      await geste(calepinageId)
      await relire()
      onApres?.()
    } finally {
      setEnCours(false)
    }
  }
  return (
    <section className="cal-tel-note" role="status" data-testid="releve-anciennes">
      <span>Relevé enregistré avant la mise à jour — à vérifier</span>
      <button type="button" className="cal-tel-pied-secondaire" disabled={enCours}
        onClick={() => agir(adopterAnciennes)} data-testid="releve-anciennes-envoyer">Envoyer sous mon compte</button>
      <button type="button" className="cal-tel-pied-secondaire" disabled={enCours}
        onClick={() => agir(supprimerAnciennes)} data-testid="releve-anciennes-supprimer">Supprimer</button>
    </section>
  )
}
