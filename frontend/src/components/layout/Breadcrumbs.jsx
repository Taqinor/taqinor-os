// I35 / I137 — Fil d'Ariane dérivé de la route courante. Les parents servent de
// contexte (libellé de section) ; seul le dernier élément est la page courante.
//
// I137 — Accessibilité + troncature :
//   • le fil est un point de repère `nav[aria-label]` ;
//   • le dernier segment (page courante) porte `aria-current="page"` et n'est
//     PAS un lien ;
//   • les chemins LONGS sont tronqués AU MILIEU : on garde le premier, les deux
//     derniers, et on remplace les segments intermédiaires par un débordement
//     « … » dont l'info-bulle (title) liste les libellés masqués ;
//   • chaque libellé porte son `title` (info-bulle plein libellé) et est tronqué
//     visuellement en CSS si trop large.
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { breadcrumbsFor } from './routes.meta'

// Au-delà de ce nombre de segments, on tronque au milieu. On conserve toujours
// le premier segment + les deux derniers (avant-dernier + page courante).
const MAX_VISIBLE = 3

// VX11 — mémoire du dernier module visité (survit au refresh), lue par VX46
// (« Mes préférences » → module d'atterrissage au login). Accès défensif,
// jamais d'exception si le stockage est indisponible (patron COLLAPSE_KEY,
// Layout.jsx:16).
const LAST_MODULE_KEY = 'taqinor.lastModule'

function persistLastModule(pathname) {
  try {
    const seg = (pathname || '').split('/').filter(Boolean)[0]
    if (seg) window.localStorage.setItem(LAST_MODULE_KEY, seg)
  } catch { /* stockage indisponible : on ignore, aucun impact sur la nav */ }
}

function Crumb({ c, withSep }) {
  return (
    <span className="breadcrumb-segment">
      {withSep && (
        <ChevronRight className="breadcrumb-sep" size={13} aria-hidden="true" />
      )}
      {c.to && !c.current ? (
        <Link to={c.to} className="breadcrumb-link" title={c.label}>{c.label}</Link>
      ) : (
        <span
          className={c.current ? 'breadcrumb-current' : 'breadcrumb-text'}
          title={c.label}
          aria-current={c.current ? 'page' : undefined}
        >
          {c.label}
        </span>
      )}
    </span>
  )
}

export default function Breadcrumbs({ pathname, crumbs: crumbsProp }) {
  const crumbs = crumbsProp ?? breadcrumbsFor(pathname || '/')

  // VX11 — persiste le dernier module à CHAQUE navigation (effet, jamais un
  // setState synchrone en phase de rendu) ; avant tout early return, comme
  // toujours pour les hooks React.
  useEffect(() => {
    persistLastModule(pathname)
  }, [pathname])

  if (crumbs.length === 0) return null

  // I137 — Troncature au milieu pour les chemins longs.
  let head = crumbs
  let hidden = []
  let tail = []
  if (crumbs.length > MAX_VISIBLE) {
    head = crumbs.slice(0, 1)
    hidden = crumbs.slice(1, crumbs.length - 2)
    tail = crumbs.slice(crumbs.length - 2)
  }
  const hiddenTitle = hidden.map((c) => c.label).join(' › ')

  return (
    <nav className="breadcrumbs" aria-label="Fil d'Ariane">
      {head.map((c, i) => (
        <Crumb key={`h-${i}`} c={c} withSep={i > 0} />
      ))}
      {hidden.length > 0 && (
        <span className="breadcrumb-segment">
          <ChevronRight className="breadcrumb-sep" size={13} aria-hidden="true" />
          <span
            className="breadcrumb-overflow"
            title={hiddenTitle}
            aria-label={`Segments masqués : ${hiddenTitle}`}
          >
            …
          </span>
        </span>
      )}
      {tail.map((c, i) => (
        <Crumb key={`t-${i}`} c={c} withSep />
      ))}
    </nav>
  )
}
