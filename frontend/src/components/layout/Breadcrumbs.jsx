// I35 — Fil d'Ariane dérivé de la route courante. Les parents servent de
// contexte (libellé de section) ; seul le dernier élément est la page courante.
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { breadcrumbsFor } from './routes.meta'

export default function Breadcrumbs({ pathname }) {
  const crumbs = breadcrumbsFor(pathname || '/')
  if (crumbs.length === 0) return null
  return (
    <nav className="breadcrumbs" aria-label="Fil d'Ariane">
      {crumbs.map((c, i) => (
        <span key={i} className="breadcrumb-segment">
          {i > 0 && <ChevronRight className="breadcrumb-sep" size={13} aria-hidden="true" />}
          {c.to && !c.current ? (
            <Link to={c.to} className="breadcrumb-link">{c.label}</Link>
          ) : (
            <span className={c.current ? 'breadcrumb-current' : 'breadcrumb-text'}
                  aria-current={c.current ? 'page' : undefined}>
              {c.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  )
}
