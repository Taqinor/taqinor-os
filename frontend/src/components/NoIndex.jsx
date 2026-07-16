import { useEffect } from 'react'

/**
 * VX202 — Composant partagé, monté par chaque page PUBLIQUE tokenisée
 * (/rdv/:token, /ged/depot|signature|signataire/:token, /suivi/:token,
 * /kb/public/:token…) : une URL prévisible ne l'est pas, mais un lien
 * tokenisé partagé par email/SMS peut fuiter (forward, capture d'écran d'un
 * historique, cache d'un proxy tiers) — sans <meta name="robots"> AUCUNE de
 * ces pages ne dit explicitement aux crawlers de ne pas les indexer.
 *
 * Pas de react-helmet (aucune dépendance ajoutée) : manipulation directe de
 * `document.head`, nettoyée au démontage (une navigation SPA vers une page
 * NON publique ne doit pas hériter du noindex).
 */
export default function NoIndex() {
  useEffect(() => {
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    document.head.appendChild(meta)
    return () => {
      if (meta.parentNode) meta.parentNode.removeChild(meta)
    }
  }, [])

  return null
}
