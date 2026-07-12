import { Link } from 'react-router-dom'

/* VX177 — navigation standalone PWA maîtrisée. En mode `standalone` iOS, un
   <a target="_blank"> externe (GED/KB/RH/wa.me/verifierIceUrl…) ouvre un
   SFSafariViewController sans retour naturel vers la coquille installée —
   c'est le comportement VOULU pour un lien réellement externe (site tiers,
   ou un document/fichier `/api/…`/`/media/…` servi par le backend, qui n'est
   PAS une route SPA). Le vrai bug est le SYMÉTRIQUE : un lien vers une route
   de l'app posé en `<a href>` nu fait une navigation plein document qui
   ÉJECTE hors de la coquille PWA (perd l'état React, recharge tout) au lieu
   d'un changement de route client-side. `ExternalLink` détecte ce SEUL cas
   (chemin `/…` qui n'est ni une API ni un fichier backend) et route via
   react-router `<Link>` ; tout le reste (site tiers, `/api/…`, `/media/…`)
   garde `_blank`+`noopener`. */
function isInternalPath(href) {
  return typeof href === 'string'
    && href.startsWith('/')
    && !href.startsWith('//')
    && !href.startsWith('/api/')
    && !href.startsWith('/media/')
}

export function ExternalLink({ href, to, children, className, ...props }) {
  const target = to ?? href
  if (isInternalPath(target)) {
    return (
      <Link to={target} className={className} {...props}>
        {children}
      </Link>
    )
  }
  return (
    <a href={target} target="_blank" rel="noopener noreferrer" className={className} {...props}>
      {children}
    </a>
  )
}

// VX177 — équivalent programmatique (onClick, pas de JSX) : même règle
// interne/externe. Ne fait rien si `url` est vide/absent (no-op défensif,
// comme les autres helpers navigateur du repo).
export function openExternal(url) {
  if (!url) return
  if (isInternalPath(url)) {
    // Pas de react-router disponible hors composant : on laisse l'appelant
    // utiliser `navigate()` pour l'interne — `openExternal` est réservé au
    // VRAI externe (l'appel sur un chemin interne est un usage incorrect).
    return
  }
  if (typeof window === 'undefined') return
  window.open(url, '_blank', 'noopener,noreferrer')
}

export default ExternalLink
