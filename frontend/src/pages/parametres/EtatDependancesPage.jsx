import { useEffect, useState } from 'react'
import { Cable } from 'lucide-react'
import coreApi from '../../api/coreApi'
import { Badge, Card, CardContent, Spinner } from '../../ui'

/* ============================================================================
   NTOBS11 — Paramètres → Fiabilité → État des dépendances. Combine les
   statuts réels (core.health.check_services) avec la matrice d'impact
   humain (core.degraded_mode.DEGRADED_MODE_MATRIX, versionnée dans le code)
   pour montrer, dépendance par dépendance, ce qui reste fonctionnel.
   ========================================================================== */

const STATUT_LABEL = {
  ok: 'Opérationnel',
  degraded: 'Dégradé',
  down: 'Panne',
  unknown: 'Inconnu',
}
const STATUT_TONE = {
  ok: 'success',
  degraded: 'warning',
  down: 'danger',
  unknown: 'neutral',
}

export default function EtatDependancesPage() {
  const [dependances, setDependances] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let active = true
    coreApi.degradedMode.getStatus()
      .then((r) => { if (active) setDependances(r.data ?? []) })
      .catch(() => { if (active) setErreur("Impossible de charger l'état des dépendances.") })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center py-16"><Spinner /></div>
  }
  if (erreur) {
    return <div className="p-6 text-sm text-destructive">{erreur}</div>
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-2">
        <Cable className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="text-xl font-semibold">État des dépendances</h1>
      </div>
      <div className="space-y-3">
        {dependances.map((dep) => (
          <Card key={dep.cle}>
            <CardContent className="space-y-2 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{dep.label}</p>
                <Badge tone={STATUT_TONE[dep.statut] || 'neutral'}>
                  {STATUT_LABEL[dep.statut] || dep.statut}
                </Badge>
              </div>
              {dep.impactees.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Impacté si en panne :</p>
                  <ul className="ml-4 list-disc text-xs text-muted-foreground">
                    {dep.impactees.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
              {dep.continuent.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Continue de fonctionner :</p>
                  <ul className="ml-4 list-disc text-xs text-muted-foreground">
                    {dep.continuent.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
