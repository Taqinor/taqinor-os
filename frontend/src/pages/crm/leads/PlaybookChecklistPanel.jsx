// NTCRM13 — Widget « Tâches du playbook » sur la fiche lead : checklist par
// étape courante, cohérente visuellement avec le pattern checklist chantier
// existant (N4). Coche/décoche une tâche via `leads/{id}/playbook/`.
import { useCallback, useEffect, useState } from 'react'
import api from '../../../api/axios'
import { Spinner, Checkbox, Card, Button } from '../../../ui'
import { toast } from '../../../ui/confirm'
import MessageVisiteDialog from '../../../features/crm/relances/MessageVisiteDialog'

export default function PlaybookChecklistPanel({ leadId }) {
  const [progress, setProgress] = useState([])
  const [loading, setLoading] = useState(true)
  // AGR527 — la clé du texte (`cle_message`, contrat `lead_playbook.json`)
  // dont l'aperçu est ouvert ; null = modale fermée.
  const [cleTexte, setCleTexte] = useState(null)

  const load = useCallback(() => {
    if (!leadId) return
    setLoading(true)
    api.get(`/crm/leads/${leadId}/playbook/`)
      .then((res) => setProgress(res.data || []))
      .catch(() => toast.error('Impossible de charger la checklist du playbook.'))
      .finally(() => setLoading(false))
  }, [leadId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
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
            {/* AGR527 — le texte de la tâche (dossier FDA / 82-21) : aperçu
                FR/darija puis « Ouvrir WhatsApp » au clic humain ; cocher la
                tâche reste un geste séparé. */}
            {p.cle_message && (
              <Button
                type="button" size="sm" variant="outline"
                data-cle-message={p.cle_message}
                onClick={() => setCleTexte(p.cle_message)}
              >
                Proposer le texte
              </Button>
            )}
          </li>
        ))}
      </ul>
      {cleTexte && (
        <MessageVisiteDialog
          leadId={leadId} cle={cleTexte} open
          onOpenChange={(ouvert) => { if (!ouvert) setCleTexte(null) }}
        />
      )}
    </Card>
  )
}
