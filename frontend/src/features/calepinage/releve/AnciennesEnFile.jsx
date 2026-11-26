import { useCallback, useEffect, useState } from 'react'
import { adopterAnciennes, anciennesEnFile, supprimerAnciennes } from '../fileEnvoiPhotos'

const AUCUNE = { releve: false, photos: 0 }

/** Le libellé de ce qui attend un choix : le relevé, puis les photos (accordées). */
function texteAnciennes({ releve, photos }) {
  const morceaux = []
  if (releve) morceaux.push('Relevé enregistré avant la mise à jour — à vérifier')
  if (photos) {
    morceaux.push(`${photos} photo${photos > 1 ? 's' : ''} gardée${photos > 1 ? 's' : ''} avant la mise à jour — à vérifier`)
  }
  return morceaux.join(' · ')
}

/* Revue ACAL1949 (points 3 et 4) — ce qui a été gardé sur cet appareil AVANT la règle « une entrée = son utilisateur »
   (relevé ou photos, aucun utilisateur noté) n'est ni envoyé seul ni jeté en silence : l'utilisateur connecté le voit
   ici et choisit. Rien n'est montré tant que la session n'est pas connue. `onApres()` : relancer le rejeu ordinaire. */
export default function AnciennesEnFile({ calepinageId, onApres }) {
  const [anciennes, setAnciennes] = useState(AUCUNE)
  const [enCours, setEnCours] = useState(false)
  const relire = useCallback(
    () => Promise.resolve(anciennesEnFile(calepinageId)).then((a) => setAnciennes(a ?? AUCUNE)).catch(() => {}),
    [calepinageId],
  )
  useEffect(() => { if (calepinageId) relire() }, [calepinageId, relire])

  if (!anciennes.releve && !anciennes.photos) return null
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
      <span>{texteAnciennes(anciennes)}</span>
      <button type="button" className="cal-tel-pied-secondaire" disabled={enCours}
        onClick={() => agir(adopterAnciennes)} data-testid="releve-anciennes-envoyer">Envoyer sous mon compte</button>
      <button type="button" className="cal-tel-pied-secondaire" disabled={enCours}
        onClick={() => agir(supprimerAnciennes)} data-testid="releve-anciennes-supprimer">Supprimer</button>
    </section>
  )
}
