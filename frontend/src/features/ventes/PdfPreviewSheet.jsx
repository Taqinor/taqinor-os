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
import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { Download, ExternalLink, RotateCcw } from 'lucide-react'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { Button, Spinner, EmptyState } from '../../ui'
import { openPdfBlob, ouvrirPdfBlob } from '../../utils/pdfBlob'

// pdfjs est lourd : il ne doit jamais entrer dans le chunk de la liste.
const PdfCanvas = lazy(() => import('./PdfCanvas'))

export default function PdfPreviewSheet({
  open,
  onOpenChange,
  title,
  description,
  filename,
  fetchBlob,
}) {
  const [blob, setBlob] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // Le rendu canvas peut échouer (PDF corrompu, mémoire) : on bascule alors
  // sur le repli d'actions plutôt que de laisser un cadre vide.
  const [renderFailed, setRenderFailed] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  // Un aperçu rouvert pendant qu'un précédent chargement est en vol ne doit
  // jamais afficher le PDF du document précédent.
  const runIdRef = useRef(0)

  const load = useCallback(async () => {
    if (!fetchBlob) return
    const runId = runIdRef.current + 1
    runIdRef.current = runId
    setLoading(true)
    setError(null)
    setRenderFailed(false)
    try {
      const b = await fetchBlob()
      if (runIdRef.current !== runId) return
      setBlob(b)
    } catch (err) {
      if (runIdRef.current !== runId) return
      setBlob(null)
      setError(err?.message || 'Aperçu indisponible.')
    } finally {
      if (runIdRef.current === runId) setLoading(false)
    }
  }, [fetchBlob])

  useEffect(() => {
    if (!open) {
      setBlob(null)
      setError(null)
      setRenderFailed(false)
      return
    }
    load()
  }, [open, load, reloadKey])

  const showFallback = !loading && (!!error || renderFailed || !blob)

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
        {loading && (
          <p className="ldp-pdf-loading">
            <Spinner /> Préparation de l'aperçu…
          </p>
        )}
        {showFallback && (
          <EmptyState
            className="p-6"
            title="Aperçu indisponible"
            description={error || 'Le rendu de l’aperçu n’a pas abouti — le document reste téléchargeable.'}
            action={(
              <Button variant="outline" size="sm" onClick={() => setReloadKey(k => k + 1)}>
                <RotateCcw /> Réessayer
              </Button>
            )}
          />
        )}
        {!loading && !showFallback && (
          <Suspense fallback={<p className="ldp-pdf-loading"><Spinner /> Chargement de l'aperçu…</p>}>
            <PdfCanvas blob={blob} onError={() => setRenderFailed(true)} />
          </Suspense>
        )}
      </div>
    </ResponsiveDialog>
  )
}
