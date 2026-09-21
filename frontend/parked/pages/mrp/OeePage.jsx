// NTMFG12 — TRS/OEE par poste de charge : une carte par poste
// (disponibilité × performance × qualité), comparaison inter-postes, sur
// les 28 derniers jours (fenêtre par défaut du backend).
import { useEffect, useState } from 'react'
import { Gauge } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import { Card, CardContent, Badge, Spinner, EmptyState, Progress } from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

function toneForTrs(pct) {
  const v = Number(pct)
  if (v >= 85) return 'success'
  if (v >= 60) return 'warning'
  return 'danger'
}

function OeeCard({ poste }) {
  return (
    <Card className="mb-3">
      <CardContent>
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-medium">{poste.poste_nom}</h3>
          <Badge tone={toneForTrs(poste.trs_pct)}>TRS {poste.trs_pct}%</Badge>
        </div>
        {!poste.donnees && (
          <div className="text-sm text-muted-foreground">
            Aucune opération terminée sur la période.
          </div>
        )}
        {poste.donnees && (
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-muted-foreground">Disponibilité</div>
              <Progress value={Number(poste.disponibilite_pct)} />
              <div>{poste.disponibilite_pct}%</div>
            </div>
            <div>
              <div className="text-muted-foreground">Performance</div>
              <Progress value={Number(poste.performance_pct)} />
              <div>{poste.performance_pct}%</div>
            </div>
            <div>
              <div className="text-muted-foreground">Qualité</div>
              <Progress value={Number(poste.qualite_pct)} />
              <div>{poste.qualite_pct}%</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function OeePage() {
  const [postes, setPostes] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    mrpApi.getOeeTousPostes({})
      .then((resp) => setPostes(resp.data || []))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <PageHeader
        title="TRS / OEE par poste de charge"
        subtitle="Disponibilité × performance × qualité — 28 derniers jours."
        icon={Gauge}
      />
      {loading && <Spinner />}
      {!loading && postes.length === 0 && (
        <EmptyState title="Aucun poste de charge actif." />
      )}
      {!loading && postes.map((poste) => (
        <OeeCard key={poste.poste_id} poste={poste} />
      ))}
    </div>
  )
}
