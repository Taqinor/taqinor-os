/* QJR653 — le CORPS d'aperçu PDF partagé (chargement, rendu PdfCanvas
   paresseux, repli, recharger), monté par PdfPreviewSheet et par le panneau
   devis du lead. L'état vient de usePdfPreview ; l'appelant ne fournit que le
   message d'échec serveur et les actions de repli propres à son écran. */
import { Suspense, lazy } from 'react'
import { RotateCcw, TriangleAlert } from 'lucide-react'
import { Button, Spinner, EmptyState } from '../../ui'
import { previewView, PREVIEW_VIEW } from './previewPdf'

// pdfjs est lourd : il ne doit jamais entrer dans le chunk de la liste.
const PdfCanvas = lazy(() => import('./PdfCanvas'))

export default function PdfPreviewBody({
  blob,
  loading,
  errorKind,
  errorMessage,
  renderFailed,
  onRenderError,
  onReload,
  reloadKey,
  loadingText = 'Préparation de l’aperçu…',
  // Message d'un VRAI échec de génération serveur (4xx/5xx) ; absent → le
  // repli générique affiche le message de l'erreur.
  serverMessage,
  serverActions,
  fallbackDescription,
  fallbackActions,
}) {
  const serverShown = errorKind === 'server' && !!serverMessage
  const view = previewView({
    loading,
    serverError: serverShown,
    blocked: (!!errorKind && !serverShown) || renderFailed || (!loading && !blob),
    hasUrl: !!blob,
  })
  const reessayer = (
    <Button type="button" variant="outline" size="sm" onClick={onReload}>
      <RotateCcw /> Réessayer
    </Button>
  )

  return (
    <>
      {view === PREVIEW_VIEW.LOADING && (
        <p className="ldp-pdf-loading"><Spinner /> {loadingText}</p>
      )}
      {view === PREVIEW_VIEW.ERROR && (
        <EmptyState
          role="alert"
          className="ldp-fallback"
          icon={TriangleAlert}
          title="Aperçu indisponible"
          description={serverMessage}
          action={(
            <div className="ldp-fallback-actions">
              {serverActions}
              {reessayer}
            </div>
          )}
        />
      )}
      {view === PREVIEW_VIEW.FALLBACK && (
        <EmptyState
          className="p-6"
          title="Aperçu indisponible"
          description={fallbackDescription || errorMessage
            || 'Le rendu de l’aperçu n’a pas abouti — le document reste téléchargeable.'}
          action={(
            <div className="ldp-fallback-stack">
              {fallbackActions && (
                <div className="ldp-fallback-actions">{fallbackActions}</div>
              )}
              {reessayer}
            </div>
          )}
        />
      )}
      {view === PREVIEW_VIEW.PDF && (
        <Suspense fallback={<p className="ldp-pdf-loading"><Spinner /> Chargement de l'aperçu…</p>}>
          <PdfCanvas key={reloadKey} blob={blob} onError={onRenderError} />
        </Suspense>
      )}
    </>
  )
}
