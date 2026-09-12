import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent, Spinner } from '../../ui'

/* ============================================================================
   NTOBS16 — Paramètres → Fiabilité → SLA. Destination du lien « Voir le
   rapport SLA complet » du badge du Dashboard (NTOBS16) — historique 12 mois
   de core.SlaSnapshot (NTOBS3), lecture seule. Pour le PDF d'un mois donné,
   voir GET /core/sla/<periode>/export-pdf/ (non branché ici — hors
   périmètre de ce widget, un futur bouton pourra l'ajouter).
   ========================================================================== */

function formatPeriode(iso) {
  try {
    return new Date(iso).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  } catch {
    return iso
  }
}

export default function SlaReportPage() {
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let active = true
    parametresApi.getSlaSnapshots()
      .then((r) => { if (active) setSnapshots(r.data ?? []) })
      .catch(() => { if (active) setErreur('Impossible de charger le rapport SLA.') })
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
        <ShieldCheck className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="text-xl font-semibold">Rapport SLA</h1>
      </div>
      {snapshots.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun rapport SLA généré pour le moment.</p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {snapshots.map((s) => (
            <li key={s.id} className="flex items-center justify-between px-4 py-3">
              <span className="text-sm capitalize">{formatPeriode(s.periode)}</span>
              <span className="text-sm font-medium">{Number(s.uptime_pct).toFixed(2)}% disponible</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
