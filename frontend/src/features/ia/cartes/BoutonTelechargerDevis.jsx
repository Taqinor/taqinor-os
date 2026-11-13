import { useState } from 'react'
import { FileDown } from 'lucide-react'
import { Button } from '../../../ui'
import ventesApi from '../../../api/ventesApi'
import { downloadBlobInGesture, filenameFromResponse } from '../../../utils/downloadBlob'
import { idDevisSur } from './cartes'

/* COP-F3/F4 — téléchargement authentifié d'un devis : le SEUL chemin client est
   `/proposal` (règle #4), récupéré en blob par `ventesApi.getProposalPdf` (cookie
   httpOnly, refresh silencieux) — même geste que la fiche lead. Le lien n'est
   construit que depuis un `devis_id` entier (carte `document` ou ligne de devis
   d'une `fiche_lead`), jamais depuis un `id` quelconque. */

// Options de rendu : objet plat de valeurs simples seulement (liste blanche
// vérifiée par le serveur).
function optionsSures(options) {
  if (!options || typeof options !== 'object' || Array.isArray(options)) return {}
  return Object.fromEntries(Object.entries(options)
    .filter(([, v]) => ['string', 'number', 'boolean'].includes(typeof v)))
}

export default function BoutonTelechargerDevis({
  devisId, reference = '', options = null, label = 'Télécharger', className = '',
}) {
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState('')
  const id = idDevisSur(devisId)
  if (!id) return null
  const telecharger = async () => {
    setOccupe(true)
    setErreur('')
    // Fenêtre ouverte dans le geste, avant le premier await (iOS / PWA).
    const pending = downloadBlobInGesture()
    try {
      const res = await ventesApi.getProposalPdf(id, optionsSures(options))
      pending.deliver(res.data, filenameFromResponse(res, `${reference || 'Devis'}.pdf`))
    } catch {
      try { pending.win?.close() } catch { /* fenêtre déjà fermée */ }
      setErreur('Téléchargement du PDF indisponible. Réessayez.')
    } finally {
      setOccupe(false)
    }
  }
  return (
    <span className={className}>
      <Button variant="outline" size="sm" className="min-h-10" disabled={occupe} loading={occupe} onClick={telecharger}>
        <FileDown className="size-4" aria-hidden="true" />
        {label}
      </Button>
      {erreur && <span className="ml-2 text-xs text-destructive" role="alert">{erreur}</span>}
    </span>
  )
}
