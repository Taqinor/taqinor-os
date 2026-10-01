/* QJR653 — LA machine d'états de l'aperçu PDF, partagée par PdfPreviewSheet
   (liste des devis / factures) et le panneau devis du lead.

   `fetchBlob(signal)` fournit les octets (l'appelant connaît seul l'URL — règle
   #4 : les devis passent par /proposal). Chaque nouveau chargement ABANDONNE
   la requête précédente (AbortController : un rendu à froid d'environ 26 s ne
   doit pas s'empiler sur les workers) ET un runId écarte toute réponse tardive
   d'un chargement périmé. */
import { useCallback, useEffect, useRef, useState } from 'react'
import { classifyFetchError } from './previewPdf'

export function usePdfPreview(fetchBlob, { enabled = true } = {}) {
  const [blob, setBlob] = useState(null)
  const [loading, setLoading] = useState(!!enabled)
  // errorKind : 'server' (4xx/5xx = vrai échec de génération) | 'network' | null.
  const [errorKind, setErrorKind] = useState(null)
  const [errorMessage, setErrorMessage] = useState(null)
  // Le rendu canvas peut échouer (PDF corrompu, mémoire) : repli d'actions.
  const [renderFailed, setRenderFailed] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const runIdRef = useRef(0)
  const controllerRef = useRef(null)

  const abortEnCours = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
  }, [])

  const load = useCallback(async () => {
    if (!fetchBlob) return
    abortEnCours()
    const controller = new AbortController()
    controllerRef.current = controller
    const runId = runIdRef.current + 1
    runIdRef.current = runId
    setLoading(true)
    setErrorKind(null)
    setErrorMessage(null)
    setRenderFailed(false)
    setBlob(null)
    try {
      const b = await fetchBlob(controller.signal)
      if (runIdRef.current !== runId) return
      setBlob(b)
    } catch (err) {
      if (runIdRef.current !== runId) return
      setBlob(null)
      setErrorKind(classifyFetchError(err))
      setErrorMessage(err?.message || 'Aperçu indisponible.')
    } finally {
      if (runIdRef.current === runId) setLoading(false)
    }
  }, [fetchBlob, abortEnCours])

  useEffect(() => {
    if (!enabled) {
      // Fermeture : requête avortée, octets relâchés (un blob multi-Mo n'a rien
      // à faire en mémoire une fois l'aperçu fermé) ; la réouverture recharge.
      runIdRef.current += 1
      abortEnCours()
      // eslint-disable-next-line react-hooks/set-state-in-effect -- purge à la fermeture, aucune cascade
      setBlob(null)
      setLoading(false)
      setErrorKind(null)
      setErrorMessage(null)
      setRenderFailed(false)
      return undefined
    }
    load()
    return () => {
      runIdRef.current += 1
      abortEnCours()
    }
  }, [enabled, load, reloadKey, abortEnCours])

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])
  const onRenderError = useCallback(() => setRenderFailed(true), [])

  return {
    blob, loading, errorKind, errorMessage, renderFailed, reload, onRenderError,
    reloadKey,
  }
}

export default usePdfPreview
