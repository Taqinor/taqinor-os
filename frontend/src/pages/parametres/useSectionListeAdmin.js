import { useCallback, useEffect, useState } from 'react'
import { useCanModifierParametres } from '../../features/parametres/useCanModifierParametres'
import { useConfirmDialog } from '../../ui/confirm'

/* État commun des sections Paramètres « liste éditable par un admin »
   (Modèles brandés) : droit d'écrire, lignes lues sur
   `url` (paginées ou non), chargement/erreur de chargement, opération en cours,
   et la confirmation de suppression MAISON (APAR41 — jamais window.confirm).
   Un seul endroit au lieu d'une copie par section (check_duplicats_litteraux).
   `charger()` relit la liste (après une création/suppression). */
/* `lire` : fonction sans argument qui renvoie une Promise de tableau de lignes — l'appelant
   garde son URL et ses paramètres visibles (gardes ENF D1 / ADOC38) : toutesLesPages(...) pour
   un endpoint paginé, api.get(url) pour un endpoint non paginé. */
export default function useSectionListeAdmin(lire) {
  const { confirmDelete } = useConfirmDialog()
  // ADRG84 — `core/branded-templates/` exige `parametres_modifier` (APAR38).
  const canManage = useCanModifierParametres()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)

  const charger = useCallback(() => Promise.resolve().then(lire)
    .then((rows) => {
      setRows(rows)
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false)), [lire])

  useEffect(() => { charger() }, [charger])

  return {
    confirmerSuppression: confirmDelete, canManage,
    rows, loading, loadError, busy, setBusy, charger,
  }
}
