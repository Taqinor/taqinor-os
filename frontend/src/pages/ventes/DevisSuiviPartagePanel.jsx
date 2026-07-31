import { Eye, Send } from 'lucide-react'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR96 — Panneau « Suivi du partage » de la fiche devis.
   ----------------------------------------------------------------------------
   Rend les deux traces marketing qui étaient jusqu'ici écrites nulle part et
   affichées nulle part :
     - `marketing.OuverturePartage` : « vu le JJ/MM à HH:MM » + nombre
       d'ouvertures du lien de proposition ;
     - `marketing.RelanceDevisAbandonne` : la liste des relances consignées.
   Données lues via `ventesApi.getSuiviPartageDevis` (agrégat serveur borné
   société). Aucun montant, aucun coût, aucune marge n'est rendu ici.
   ========================================================================== */

export default function DevisSuiviPartagePanel({ data, loading }) {
  if (loading) {
    return <p className="text-xs text-muted-foreground">Chargement…</p>
  }

  const ouverture = data?.ouverture || null
  const relances = data?.relances || []

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2">
        <Eye className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden="true" />
        {ouverture ? (
          <p className="text-sm">
            Vu le{' '}
            <strong>
              {ouverture.premier_vu_le ? formatDateTime(ouverture.premier_vu_le) : '—'}
            </strong>
            {ouverture.dernier_vu_le
              && ouverture.dernier_vu_le !== ouverture.premier_vu_le && (
              <>
                {' · dernière consultation '}
                {formatDateTime(ouverture.dernier_vu_le)}
              </>
            )}
            {' · '}
            {ouverture.nb_ouvertures} ouverture{ouverture.nb_ouvertures > 1 ? 's' : ''}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Lien de proposition jamais ouvert.
          </p>
        )}
      </div>

      <div className="flex items-start gap-2">
        <Send className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">
            Relances consignées
          </p>
          {relances.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune relance consignée.</p>
          ) : (
            <ul className="mt-1 space-y-1 text-sm">
              {relances.map((r) => (
                <li key={r.id} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-xs text-muted-foreground">
                    {r.date_relance ? formatDateTime(r.date_relance) : '—'}
                  </span>
                  <span>
                    {r.canal || 'canal inconnu'}
                    {r.jours_sans_reponse
                      ? ` · ${r.jours_sans_reponse} j sans réponse`
                      : ''}
                  </span>
                  {r.note && (
                    <span className="text-xs text-muted-foreground">{r.note}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
