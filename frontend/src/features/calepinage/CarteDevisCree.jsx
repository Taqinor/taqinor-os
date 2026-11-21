import { Link } from 'react-router-dom'

/* ACAL866 — la carte de succès de « Générer le devis » : dit que le devis est créé (référence
   servie, jamais inventée) et ouvre le VRAI devis (`/ventes/devis?devis=<id>`, lignes, total, PDF).
   Les lignes techniques (verdict électrique, avertissements) sont repliées pour le technicien. */
export default function CarteDevisCree({ devisId, reference = null, onRevenir = null, children = null, aDetails = false }) {
  return (
    <div className="border border-brass-400/40 p-3" role="status" data-testid="cal-devis-cree">
      <p className="text-sm font-semibold text-foreground">
        {reference ? `Devis ${reference} créé` : 'Devis créé'}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Link
          to={`/ventes/devis?devis=${devisId}`}
          data-testid="cal-devis-ouvrir"
          className="inline-flex min-h-11 items-center bg-brass-500/20 px-4 text-sm font-bold text-primary-text"
        >
          Voir le devis
        </Link>
        <button
          type="button"
          onClick={onRevenir ?? undefined}
          data-testid="cal-devis-revenir"
          className="inline-flex min-h-11 items-center text-sm font-semibold text-primary-text underline"
        >
          Revenir à la conception
        </button>
      </div>
      {aDetails && (
        <details className="mt-3" data-testid="cal-devis-details-technicien">
          <summary className="min-h-11 cursor-pointer py-2 text-sm text-muted-foreground">Détails pour le technicien</summary>
          {children}
        </details>
      )}
    </div>
  )
}
