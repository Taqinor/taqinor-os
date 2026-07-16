// NTCRM13 — Widget « Tâches du playbook » sur la fiche lead : checklist par
// étape courante, cohérente visuellement avec le pattern checklist chantier
// existant (N4). Coche/décoche une tâche via `leads/{id}/playbook/`.
import { useCallback, useEffect, useState } from 'react'
import api from '../../../api/axios'
import { Spinner, Checkbox, Card } from '../../../ui'
import { toast } from '../../../ui/confirm'

export default function PlaybookChecklistPanel({ leadId }) {
  const [progress, setProgress] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    if (!leadId) return
    setLoading(true)
    api.get(`/crm/leads/${leadId}/playbook/`)
      .then((res) => setProgress(res.data || []))
      .catch(() => toast.error('Impossible de charger la checklist du playbook.'))
      .finally(() => setLoading(false))
  }, [leadId])

  useEffect(() => { load() }, [load])

  const toggle = async (tacheId, fait) => {
    // Optimiste : la checklist réagit immédiatement, resynchronisée ensuite.
    setProgress((prev) => prev.map((p) => (p.tache === tacheId ? { ...p, fait } : p)))
    try {
      await api.post(`/crm/leads/${leadId}/playbook/`, { tache: tacheId, fait })
    } catch {
      toast.error('Échec de la mise à jour de la tâche.')
      load()
    }
  }

  if (loading) return <Spinner />
  if (progress.length === 0) return null // aucun playbook actif pour cette étape.

  return (
    <Card className="p-4 space-y-2" data-testid="playbook-checklist-panel">
      <h3 className="font-medium text-sm">Tâches du playbook</h3>
      <ul className="space-y-1">
        {progress.map((p) => (
          <li key={p.id} className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={p.fait}
              onCheckedChange={(checked) => toggle(p.tache, Boolean(checked))}
            />
            <span className={p.fait ? 'line-through text-muted-foreground' : ''}>
              {p.tache_libelle}
            </span>
            {p.tache_obligatoire && !p.fait && (
              <span className="text-xs text-destructive">obligatoire</span>
            )}
            {p.fait && p.fait_par_nom && (
              <span className="text-xs text-muted-foreground">— {p.fait_par_nom}</span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}
