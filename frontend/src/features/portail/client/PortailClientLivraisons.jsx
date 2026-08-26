import { useEffect, useState } from 'react'
import { Truck } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Spinner,
} from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   WIR216 — « Mes livraisons » (portail client authentifié).
   ----------------------------------------------------------------------------
   Le lien de l'email `livraison_en_transit`/`livraison_livree` (FG228/XSTK22,
   apps.installations.livraison_client_notify) pointait vers une section
   INEXISTANTE — 404 systématique. Lecture SEULE, scopée serveur au client
   connecté (jamais un id de client envoyé par le front) via
   `apps.installations.selectors.livraisons_client_portail` : jamais
   `cout_transport` ni un prix d'achat, seulement référence/date prévue/statut/
   numéro de suivi/articles (désignation+quantité) + preuve de livraison (POD)
   une fois livrée.
   ========================================================================== */

const TON_STATUT = {
  planifiee: 'neutral',
  en_transit: 'info',
  livree: 'success',
  annulee: 'neutral',
}

export default function PortailClientLivraisons() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  const charger = () => {
    setLoading(true)
    portailApi.livraisons.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // Différé d'un microtask : `charger` pose l'état de chargement de façon
    // synchrone, ce qui déclenche un rendu en cascade
    // (react-hooks/set-state-in-effect). Même patron que PortailClientDevis/
    // PortailClientFactures.
    Promise.resolve().then(charger)
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
                    {l.date_prevue
                      ? `Prévue le ${formatDate(l.date_prevue)}`
                      : 'Date prévue non communiquée'}
                    {l.numero_suivi ? ` — suivi ${l.numero_suivi}` : ''}
                  </p>
                </div>
                <Badge tone={TON_STATUT[l.statut] || 'neutral'}>
                  {l.statut_display}
                </Badge>
              </div>

              {l.articles?.length > 0 && (
                <ul className="flex flex-col gap-1 text-sm">
                  {l.articles.map((a, i) => (
                    <li key={i} className="text-muted-foreground">
                      {a.designation || 'Article'} × {a.quantite}
                    </li>
                  ))}
                </ul>
              )}

              {l.pod_disponible && (
                <div>
                  <Button asChild variant="outline" size="sm">
                    <a href={l.pod_url} target="_blank" rel="noreferrer">
                      Voir la preuve de livraison
                    </a>
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
