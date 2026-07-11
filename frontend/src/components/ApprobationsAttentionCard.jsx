// VX86 — Carte « Attend votre décision » en tête du Dashboard : rend visible
// la boîte d'approbations centralisée (XKB1/ZCTR7-9), jusqu'ici un 6ᵉ item
// discret de la section ANALYSE. Composant AUTONOME (son propre appel API,
// comme `MesEquipesCard`/`ImpactPastille`) : rend NULL tant que rien n'est
// chargé ou si le total est 0 — jamais de carte vide. Réutilise
// `useApprobationsCount` pour le TOTAL (cohérent avec le badge nav/la cloche)
// et un appel séparé top-3 (`?trier=urgence`) pour la liste — même endpoint,
// tri déjà supporté côté backend. company + acting user résolus SERVEUR.
//
// MINIMAL par construction (le spec VX86 le demande explicitement) pour ne
// pas empiéter sur VX27 (dashboards par rôle, qui fusionnera cette carte à
// son build) ni VX14.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Inbox, ChevronRight } from 'lucide-react'
import reportingApi from '../api/reportingApi'
import { useApprobationsCount } from '../hooks/useApprobationsCount'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Button } from '../ui'
import { formatNumber } from '../lib/format'

const SOURCE_LABELS = {
  automation: 'Automatisation',
  contrats: 'Contrats',
  ged: 'GED',
  installations: 'Installations',
  workflow: 'Workflow',
}

export default function ApprobationsAttentionCard() {
  const navigate = useNavigate()
  const { total, loading, error } = useApprobationsCount()
  const [top, setTop] = useState([])

  useEffect(() => {
    let alive = true
    // Top-3 par urgence (en retard d'abord) — même endpoint que le total,
    // seul le tri diffère ; échec silencieux (la carte se rabat sur le total).
    reportingApi.approbationsEnAttente({ trier: 'urgence' })
      .then((r) => {
        if (!alive) return
        const items = r.data?.items ?? []
        setTop(Array.isArray(items) ? items.slice(0, 3) : [])
      })
      .catch(() => { if (alive) setTop([]) })
    return () => { alive = false }
  }, [])

  // Rien à montrer : chargement pas terminé, erreur, ou aucune approbation en
  // attente — jamais de carte vide ni de « 0 » affiché.
  if (loading || error || total === 0) return null

  return (
    <Card
      className="border-warning/30 bg-warning/5"
      data-testid="approbations-attention-card"
    >
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Inbox className="size-4 text-muted-foreground" aria-hidden="true" />
              Attend votre décision
            </CardTitle>
            <CardDescription>
              {formatNumber(total)} demande{total > 1 ? 's' : ''} en attente d'approbation
            </CardDescription>
          </div>
          <Badge tone="warning">{total > 99 ? '99+' : formatNumber(total)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {top.length > 0 && (
          <ul className="flex flex-col divide-y divide-border">
            {top.map((item) => (
              <li
                key={`${item.source}-${item.id}`}
                className="flex items-center justify-between gap-3 py-1.5 text-sm first:pt-0 last:pb-0"
              >
                <span className="min-w-0 flex-1 truncate text-foreground">
                  {item.libelle || `#${item.id}`}
                </span>
                <Badge tone="neutral">{SOURCE_LABELS[item.source] || item.source}</Badge>
              </li>
            ))}
          </ul>
        )}
        <Button
          size="sm"
          variant="secondary"
          className="self-start"
          onClick={() => navigate('/approbations')}
        >
          Voir toutes les approbations <ChevronRight className="size-3.5" aria-hidden="true" />
        </Button>
      </CardContent>
    </Card>
  )
}
