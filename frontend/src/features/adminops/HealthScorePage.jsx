import { useEffect, useState } from 'react'
import adminopsApi from './adminopsApi'
import PageHeader from '../../components/layout/PageHeader'
import { Card, Spinner } from '../../ui'
import { toastError } from '../../lib/toast'

/* ============================================================================
   NTADM6 — « Santé du compte » : jauge du health score + 3 recommandations.
   (La carte embarquée sur /dashboard est un follow-on léger ; cette page
   autonome expose la même donnée via `/adminops/health-score/`.)
   ========================================================================== */

export default function HealthScorePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminopsApi
      .healthScore()
      .then((res) => setData(res.data))
      .catch(() => toastError('Impossible de charger le health score.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (!data) return null

  return (
    <div>
      <PageHeader title="Santé du compte" subtitle="Indicateur de complétude et d'usage de votre ERP" />
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card className="p-6">
          <div className="text-5xl font-bold">{data.score}<span className="text-lg text-muted-foreground">/100</span></div>
          <div className="mt-4 space-y-2">
            {Object.entries(data.sous_scores || {}).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <span className="capitalize">{k}</span>
                <span>{v}/100</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-6">
          <h3 className="mb-3 font-semibold">Recommandations</h3>
          <ul className="list-disc space-y-2 pl-5 text-sm">
            {(data.recommandations || []).map((r, i) => (
              <li key={i}>{r}</li>
            ))}
            {(data.recommandations || []).length === 0 && (
              <li className="list-none text-muted-foreground">Tout est en ordre.</li>
            )}
          </ul>
        </Card>
      </div>
    </div>
  )
}
