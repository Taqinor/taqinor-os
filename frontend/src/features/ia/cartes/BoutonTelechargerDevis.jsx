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

// Options de rendu admises ici : le format et l'étude, nommés un à un (le
// serveur garde sa propre liste blanche, `clean_pdf_options`). Toute autre clé
// reçue dans la carte est ignorée.
function optionsSures(options) {
  const o = options && typeof options === 'object' && !Array.isArray(options) ? options : {}
  const params = {}
  if (o.pdf_mode === 'onepage' || o.pdf_mode === 'full') params.pdf_mode = o.pdf_mode
  if (typeof o.include_etude === 'boolean') params.include_etude = o.include_etude
  return params
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
      // parametres-requete: pdf_mode, include_etude
      const res = await ventesApi.getProposalPdf(id, optionsSures(options))
      pending.deliver(res.data, filenameFromResponse(res, `${reference || 'Devis'}.pdf`))
    } catch {
      // L'onglet d'attente ouvert dans le geste ne reste pas vide.
      if (pending.win && !pending.win.closed) pending.win.close()
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
