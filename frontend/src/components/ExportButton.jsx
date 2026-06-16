import { useState } from 'react'
import { downloadBlob } from '../utils/downloadBlob'

/**
 * Bouton « Exporter Excel » réutilisable et standardisé pour toutes les listes.
 *
 * Props :
 *   - fetcher : (params) => Promise<axios response blob>  (ex. crmApi.exportClients)
 *   - params  : objet des FILTRES COURANTS (mêmes query params que la liste) ;
 *               l'export les transmet au serveur → respect des filtres.
 *   - filename: nom du fichier .xlsx téléchargé.
 *   - label   : libellé (défaut « Exporter Excel »).
 */
export default function ExportButton({
  fetcher, params = {}, filename = 'export.xlsx',
  label = 'Exporter Excel', className = 'btn btn-sm btn-outline',
}) {
  const [busy, setBusy] = useState(false)

  const onClick = async () => {
    setBusy(true)
    try {
      const res = await fetcher(params)
      downloadBlob(res.data, filename)
    } catch {
      alert('Export impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <button type="button" className={className} disabled={busy}
      onClick={onClick}>
      {busy ? 'Export…' : label}
    </button>
  )
}
