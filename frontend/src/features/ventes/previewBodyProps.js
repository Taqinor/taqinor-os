// Props d'état communes tirées de usePdfPreview (ENF19 — une seule liste pour
// les deux écrans) ; `onReload` remplace `preview.reload` quand l'écran en a un.
export function previewBodyProps(preview, onReload = preview.reload) {
  return {
    blob: preview.blob,
    loading: preview.loading,
    errorKind: preview.errorKind,
    errorMessage: preview.errorMessage,
    renderFailed: preview.renderFailed,
    onRenderError: preview.onRenderError,
    onReload,
    reloadKey: preview.reloadKey,
  }
}
