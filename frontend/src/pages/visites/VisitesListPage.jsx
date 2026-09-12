// VT5 — « Mes visites » (mobile-first) : les visites techniques du commercial
// connecté, avec le badge de complétude renvoyé PAR LE SERVEUR
// (`complet`/`manquants_count`, `GET /visites/?mine=1`) — jamais recalculé
// ici. La création se fait normalement depuis la fiche lead (onglet Visite,
// VisiteTab.jsx) ; ce bouton est un second point d'entrée pour le commercial
// qui part de sa liste plutôt que d'un lead précis.
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import visitesApi from '../../api/visitesApi'
import PageHeader from '../../components/layout/PageHeader'
import { Card, Badge, Spinner, EmptyState, Segmented } from '../../ui'
import { STATUT_VISITE_LABEL } from './visiteHelpers'

export default function VisitesListPage() {
  const navigate = useNavigate()
  const [scope, setScope] = useState('mine')
  const [visites, setVisites] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setErreur(null)
    visitesApi.getVisites(scope === 'mine' ? { mine: 1 } : {})
      .then((res) => setVisites(res.data?.results ?? res.data ?? []))
      .catch(() => setErreur('Chargement des visites impossible.'))
      .finally(() => setLoading(false))
  }, [scope])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial + à chaque bascule de portée
  useEffect(() => { load() }, [load])

  return (
    <div className="page max-w-[720px]">
      <PageHeader title="Visites techniques" subtitle="Checklist photos/mesures guidée sur le terrain" />

      <div className="mb-3">
        <Segmented
          value={scope}
          onChange={setScope}
          options={[
            { value: 'mine', label: 'Mes visites' },
            { value: 'toutes', label: 'Toutes' },
          ]}
        />
      </div>

      {loading ? (
        <Spinner />
      ) : erreur ? (
        <p role="alert" className="text-sm text-destructive">{erreur}</p>
      ) : visites.length === 0 ? (
        <EmptyState
          title="Aucune visite technique"
          description="Planifiez une visite depuis la fiche d'un lead (onglet « Visite »)."
        />
      ) : (
        <ul className="space-y-2">
          {visites.map((v) => (
            <li key={v.id}>
              <Card
                role="button"
                tabIndex={0}
                className="flex min-h-11 cursor-pointer items-center justify-between gap-3 p-3"
                onClick={() => navigate(`/visites/${v.id}`)}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/visites/${v.id}`) }}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{v.lead_nom}</p>
                  <p className="text-xs text-muted-foreground">
                    {v.ville ? `${v.ville} · ` : ''}
                    {STATUT_VISITE_LABEL[v.statut] ?? v.statut}
                    {v.date_prevue ? ` · prévue le ${v.date_prevue}` : ''}
                  </p>
                </div>
                <Badge tone={v.complet ? 'success' : 'neutral'} className="shrink-0">
                  {v.complet ? 'Complète' : `${v.manquants_count ?? 0} manquant(s)`}
                </Badge>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
