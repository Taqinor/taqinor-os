import { useEffect, useState } from 'react'
import { Gauge } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Badge, Card, CardContent, Progress, Spinner } from '../../ui'

/* ============================================================================
   NTOBS8 — Paramètres → Fiabilité → Limites & usage. Écran LECTURE SEULE :
   consomme core.usage_limits.usage_summary (GET /core/usage-limites/), qui
   agrège des ressources DÉJÀ mesurées ailleurs (GED, API, import, sièges) —
   aucun nouveau compteur stocké ici.
   ========================================================================== */

function formatValeur(valeur, unite) {
  if (valeur == null) return '—'
  if (unite === 'octets') {
    if (valeur >= 1024 * 1024 * 1024) return `${(valeur / (1024 ** 3)).toFixed(1)} Go`
    if (valeur >= 1024 * 1024) return `${(valeur / (1024 ** 2)).toFixed(1)} Mo`
    if (valeur >= 1024) return `${Math.round(valeur / 1024)} Ko`
    return `${valeur} o`
  }
  return `${valeur} ${unite || ''}`.trim()
}

function toneFromPct(pct) {
  if (pct >= 100) return 'danger'
  if (pct >= 80) return 'warning'
  return 'primary'
}

function RessourceCard({ ressource }) {
  const { nom, utilise, limite, unite } = ressource
  const illimite = !limite
  const pct = illimite || utilise == null ? 0 : Math.min(100, (utilise / limite) * 100)

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">{nom}</p>
          {!illimite && pct >= 80 && (
            <Badge tone={toneFromPct(pct)}>{pct >= 100 ? 'Atteint' : 'Proche du seuil'}</Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {formatValeur(utilise, unite)}
          {illimite ? ' (illimité)' : ` / ${formatValeur(limite, unite)}`}
        </p>
        {!illimite && utilise != null && (
          <Progress value={pct} tone={toneFromPct(pct)} />
        )}
      </CardContent>
    </Card>
  )
}

export default function LimitesUsagePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let active = true
    parametresApi.getUsageLimites()
      .then((r) => { if (active) setData(r.data ?? {}) })
      .catch(() => { if (active) setErreur('Impossible de charger les limites et usages.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center py-16"><Spinner /></div>
  }
  if (erreur) {
    return <div className="p-6 text-sm text-destructive">{erreur}</div>
  }

  const ressources = data?.ressources ?? []

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <div className="flex items-center gap-2">
        <Gauge className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="text-xl font-semibold">Limites & usage</h1>
      </div>
      {ressources.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune ressource mesurable pour le moment.</p>
      ) : (
        <div className="space-y-3">
          {ressources.map((r) => <RessourceCard key={r.nom} ressource={r} />)}
        </div>
      )}
    </div>
  )
}
