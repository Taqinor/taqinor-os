import { useCallback, useEffect, useState } from 'react'
import api from '../../api/axios'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { useConfirmDialog } from '../../ui/confirm'

/* État commun des sections Paramètres « liste éditable par un admin »
   (Politiques d'approbation, Modèles brandés) : droit d'écrire, lignes lues sur
   `url` (paginées ou non), chargement/erreur de chargement, opération en cours,
   et la confirmation de suppression MAISON (APAR41 — jamais window.confirm).
   Un seul endroit au lieu d'une copie par section (check_duplicats_litteraux).
   `charger()` relit la liste (après une création/suppression). */
export default function useSectionListeAdmin(url) {
  const { confirmDelete } = useConfirmDialog()
  const canManage = useIsAdminOrResponsable()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)

  const charger = useCallback(() => api.get(url)
    .then((res) => {
      setRows(res.data?.results ?? res.data ?? [])
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false)), [url])

  useEffect(() => { charger() }, [charger])

  return {
    confirmerSuppression: confirmDelete, canManage,
    rows, loading, loadError, busy, setBusy, charger,
  }
}
