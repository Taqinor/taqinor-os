import { useEffect, useState, useCallback } from 'react'
import { Copy, ExternalLink, Eye, EyeOff } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   ADSDEEP14 — Panneau « Créatif » du détail d'une ad.
   ----------------------------------------------------------------------------
   Rend le créatif LIVE miroité (ADSDEEP11) : vidéo JOUABLE (URL fraîche
   ADSDEEP12 — jamais persistée), image, texte complet (titre/body/description/
   CTA), permalien Instagram, toggle preview iframe (ADSDEEP13), bouton copier
   le texte. Le `creative` (miroir) est passé en props ; les médias/aperçus sont
   résolus à l'affichage. Données mockées en test.
   ========================================================================== */

const PREVIEW_FORMAT = 'MOBILE_FEED_STANDARD'

export default function AdCreativePanel({ adMetaId, creative }) {
  const c = creative || {}
  const [videoUrl, setVideoUrl] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [previewHtml, setPreviewHtml] = useState('')
  const [showPreview, setShowPreview] = useState(false)
  const [copied, setCopied] = useState(false)

  // Résout l'URL JOUABLE fraîche de la vidéo (jamais persistée).
  useEffect(() => {
    let alive = true
    if (c.video_id) {
      adsengineApi.media.resolve(c.video_id, 'video')
        .then((r) => { if (alive) setVideoUrl(r.data?.url || '') })
        .catch(() => { if (alive) setVideoUrl('') })
    }
    if (c.image_hash) {
      adsengineApi.media.resolve(c.image_hash, 'image')
        .then((r) => { if (alive) setImageUrl(r.data?.url || '') })
        .catch(() => { if (alive) setImageUrl('') })
    }
    return () => { alive = false }
  }, [c.video_id, c.image_hash])

  const togglePreview = useCallback(() => {
    const next = !showPreview
    setShowPreview(next)
    if (next && !previewHtml && adMetaId) {
      adsengineApi.previews.get(adMetaId, PREVIEW_FORMAT)
        .then((r) => setPreviewHtml(r.data?.body || ''))
        .catch(() => setPreviewHtml(''))
    }
  }, [showPreview, previewHtml, adMetaId])

  const copyText = useCallback(() => {
    const text = [c.title, c.body, c.description].filter(Boolean).join('\n\n')
    try {
      navigator.clipboard?.writeText(text)
    } catch { /* clipboard indisponible : silencieux */ }
    setCopied(true)
  }, [c.title, c.body, c.description])

  return (
    <div data-testid="ae-creative-panel">
      <h3>Créatif</h3>

      {c.video_id && (
        <div data-testid="ae-creative-video">
          {videoUrl
            ? <video data-testid="ae-creative-video-el" src={videoUrl} controls />
            : <p data-testid="ae-creative-video-loading">Chargement de la vidéo…</p>}
        </div>
      )}

      {c.image_hash && imageUrl && (
        <img data-testid="ae-creative-image" src={imageUrl} alt={c.title || 'Créatif'} />
      )}

      <div data-testid="ae-creative-text">
        {c.title && <p data-testid="ae-creative-title"><strong>{c.title}</strong></p>}
        {c.body && <p data-testid="ae-creative-body">{c.body}</p>}
        {c.description && <p data-testid="ae-creative-description">{c.description}</p>}
        {c.cta_type && <p data-testid="ae-creative-cta">CTA : {c.cta_type}</p>}
      </div>

      {c.instagram_permalink_url && (
        <a
          data-testid="ae-creative-ig-link"
          href={c.instagram_permalink_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <ExternalLink size={14} aria-hidden /> Voir sur Instagram
        </a>
      )}

      <div>
        <button type="button" data-testid="ae-creative-copy" onClick={copyText}>
          <Copy size={14} aria-hidden /> {copied ? 'Copié' : 'Copier le texte'}
        </button>
        <button type="button" data-testid="ae-creative-preview-toggle" onClick={togglePreview}>
          {showPreview
            ? <><EyeOff size={14} aria-hidden /> Masquer l’aperçu</>
            : <><Eye size={14} aria-hidden /> Afficher l’aperçu</>}
        </button>
      </div>

      {showPreview && (
        <div
          data-testid="ae-creative-preview"
          // check-no-danger-allow: aperçu iframe Meta officiel (Graph API generatepreviews), proxifié via notre endpoint authentifié ADSDEEP13
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      )}
    </div>
  )
}
