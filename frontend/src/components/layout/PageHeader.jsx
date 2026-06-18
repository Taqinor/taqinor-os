// I35 — Motif d'en-tête de page réutilisable : titre + actions + filtres/onglets.
// Les pages POURRONT l'adopter plus tard ; on ne modifie aucun fichier de page
// ici, on se contente d'exporter le composant. Classes préfixées `pageheader-`
// pour ne pas entrer en conflit avec l'ancien `.page-header` des pages actuelles.
export default function PageHeader({
  title,
  subtitle,
  actions,        // noeud(s) à droite du titre (boutons, etc.)
  filters,        // barre de filtres / onglets sous le titre
  breadcrumbs,    // noeud optionnel (ex. <Breadcrumbs/>) au-dessus du titre
  className = '',
  children,
}) {
  return (
    <div className={`pageheader ${className}`.trim()}>
      <div className="pageheader-top">
        <div className="pageheader-heading">
          {breadcrumbs}
          {title && <h2 className="pageheader-title">{title}</h2>}
          {subtitle && <p className="pageheader-subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="pageheader-actions">{actions}</div>}
      </div>
      {filters && <div className="pageheader-filters">{filters}</div>}
      {children}
    </div>
  )
}
