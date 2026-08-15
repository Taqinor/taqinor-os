import { useEffect, useState } from 'react'
import { Truck, FileCheck2 } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Badge, Card, EmptyState, Spinner } from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   WIR216/XSTK22 — « Mes livraisons » (portail client authentifié).
   ----------------------------------------------------------------------------
   Le lien de l'email/WhatsApp envoyé à chaque transition de livraison
   (livraison_en_transit/livree, `apps.installations.livraison_client_notify`)
   pointait vers une route qui n'a JAMAIS existé côté frontend — 404 garanti à
   chaque expédition. Cet écran ferme le trou : liste des livraisons des
   chantiers du client (date prévue, statut, numéro de suivi, articles),
   scopée au compte connecté côté SERVEUR (`portail/mes-livraisons/`, jamais
   un client_id envoyé par l'écran). Aucune donnée interne (cout_transport,
   prix d'achat) — contrat garanti par le sélecteur
   `installations.selectors.livraisons_client_portail`.
   ========================================================================== */

const TON_STATUT = {
  planifiee: 'neutral',
  en_transit: 'info',
  livree: 'success',
  annulee: 'danger',
}

export default function PortailClientLivraisons() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    // Différé d'un microtask — même patron que PortailClientFactures.
    Promise.resolve().then(() => {
      setLoading(true)
      portailApi.livraisons.liste()
        .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
        .catch(() => setErreur(true))
        .finally(() => setLoading(false))
    })
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos livraisons…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Livraisons indisponibles"
        description="Vos livraisons n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <Truck className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes livraisons
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucune livraison"
          description="Vous n’avez aucune livraison pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((l) => (
            <Card key={l.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{l.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    {l.date_prevue ? `Prévue le ${formatDate(l.date_prevue)}` : 'Date à confirmer'}
                    {l.numero_suivi ? ` — suivi ${l.numero_suivi}` : ''}
                  </p>
                </div>
                <Badge tone={TON_STATUT[l.statut] || 'neutral'}>
                  {l.statut_display}
                </Badge>
              </div>
              {l.articles?.length > 0 && (
                <ul className="text-sm text-muted-foreground">
                  {l.articles.map((a, i) => (
                    <li key={i}>{a.designation} × {a.quantite}</li>
                  ))}
                </ul>
              )}
              {l.pod_disponible && l.pod_url && (
                <a
                  href={l.pod_url}
                  target="_blank" rel="noopener noreferrer"
                  className="flex w-fit items-center gap-1.5 text-sm font-medium text-primary hover:underline"
                >
                  <FileCheck2 className="size-4" aria-hidden="true" />
                  Preuve de livraison
                </a>
              )}
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
