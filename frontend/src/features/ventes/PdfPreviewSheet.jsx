/* APX14 — L'APERÇU PDF SANS QUITTER L'ÉCRAN (la signature « outil premium »).
   ---------------------------------------------------------------------------
   État d'avant : « Aperçu du PDF » de la liste des devis ouvrait un ONGLET,
   alors que `features/ventes/PdfCanvas.jsx` (rendu inline, inblocable) avait
   déjà QUATRE consommateurs ailleurs (panneau devis du lead, dialogue de
   signature, fiche chantier, archive documentaire) — jamais l'écran devis.

   Ce composant est l'enveloppe partagée : un panneau latéral / tiroir bas
   (`ResponsiveDialog`, zéro dépendance nouvelle) qui rend le PDF page par
   page, avec Télécharger et Ouvrir dans un onglet en REPLI.

   RÈGLE #4 — ce composant ne connaît AUCUNE URL de PDF : l'appelant lui passe
   un `fetchBlob()`. Les devis passent le moteur vendorisé `/proposal` (le
   SEUL chemin PDF devis client), les factures leur PDF legacy propre. Aucun
   chemin nouveau n'est créé ici, et rien n'y change un statut. */
import { Download, ExternalLink } from 'lucide-react'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { Button } from '../../ui'
import { openPdfBlob, ouvrirPdfBlob } from '../../utils/pdfBlob'
import { usePdfPreview } from './usePdfPreview'
import PdfPreviewBody from './PdfPreviewBody'

export default function PdfPreviewSheet({
  open,
  onOpenChange,
  title,
  description,
  filename,
  fetchBlob,
}) {
  // QJR653 — la machine d'états (chargement, abandon de la requête précédente,
  // repli) vit dans usePdfPreview ; le corps d'aperçu dans PdfPreviewBody.
  const preview = usePdfPreview(fetchBlob, { enabled: open })
  const { blob } = preview

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      className="apx-pdf-preview-dialog"
      footer={(
        <>
          <Button variant="outline" size="sm" disabled={!blob}
                  onClick={() => blob && openPdfBlob(blob, filename)}>
            <Download /> Télécharger
          </Button>
          {/* VX48 — le blob est DÉJÀ en mémoire quand ce bouton existe :
              `ouvrirPdfBlob` fait un window.open SYNCHRONE dans le geste,
              donc Safari iOS ne le bloque pas (et retombe seul sur le
              téléchargement si la popup est refusée). */}
          <Button variant="outline" size="sm" disabled={!blob}
                  onClick={() => blob && ouvrirPdfBlob(blob, filename)}>
            <ExternalLink /> Ouvrir dans un onglet
          </Button>
        </>
      )}
    >
      <div className="apx-pdf-preview" data-testid="apx-pdf-preview">
        <PdfPreviewBody
          blob={preview.blob}
          loading={preview.loading}
          errorKind={preview.errorKind}
          errorMessage={preview.errorMessage}
          renderFailed={preview.renderFailed}
          onRenderError={preview.onRenderError}
          onReload={preview.reload}
          reloadKey={preview.reloadKey}
        />
      </div>
    </ResponsiveDialog>
  )
}
