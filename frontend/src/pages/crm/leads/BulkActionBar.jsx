// Barre d'actions EN MASSE (T3) — visible dès qu'au moins un lead est coché,
// partagée par la vue liste et la vue kanban. Chaque action ouvre un petit
// contrôle en ligne puis applique via onAction(action, params) (le parent
// appelle l'API et journalise « en masse » côté serveur). L'export passe par
// onExport. Les règles du funnel sont appliquées SERVEUR — ici, on ne fait que
// présenter les actions.
import { useState } from 'react'
import { Download, X } from 'lucide-react'
import {
  PIPELINE_STAGES, STAGE_LABELS, CANAL_LABELS, PRIORITE_LABELS,
} from '../../../features/crm/stages'
import {
  Button, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'

// Radix Select interdit la valeur chaîne vide → sentinelle pour « aucun ».
const NO_OWNER = '__none'

export default function BulkActionBar({
  count, users = [], canDelete, hasArchivedSelected = false,
  busy, onAction, onExport, onClear,
}) {
  // panneau ouvert ('reassign' | 'stage' | 'tag' | 'relance' | 'perdu' | null)
  const [panel, setPanel] = useState(null)
  const [owner, setOwner] = useState('')
  const [stage, setStage] = useState(PIPELINE_STAGES[0])
  const [canal, setCanal] = useState(Object.keys(CANAL_LABELS)[0])
  const [priorite, setPriorite] = useState('normale')
  const [tag, setTag] = useState('')
  const [relance, setRelance] = useState('')
  const [motif, setMotif] = useState('')
  // Planifier une activité en masse (records.Activity) : intitulé + échéance.
  const [actSummary, setActSummary] = useState('Appeler')
  const [actDue, setActDue] = useState('')

  const toggle = (name) => setPanel((p) => (p === name ? null : name))
  const run = (action, params) => { onAction(action, params); setPanel(null) }

  return (
    <div className="bulk-bar" role="region" aria-label="Actions en masse">
      <div className="bulk-bar-count">
        <strong>{count}</strong> sélectionné{count > 1 ? 's' : ''}
      </div>

      <div className="bulk-bar-actions">
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('reassign')} disabled={busy}>
          Responsable
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('stage')} disabled={busy}>
          Étape
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('canal')} disabled={busy}>
          Canal
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('priorite')} disabled={busy}>
          Priorité
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('tag')} disabled={busy}>
          Tag
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('relance')} disabled={busy}>
          Relance
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('activity')} disabled={busy}>
          Planifier activité
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => toggle('perdu')} disabled={busy}>
          Perdu
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => run('archive')} disabled={busy}>
          Archiver
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={() => run('unarchive')}
                disabled={busy || !hasArchivedSelected}
                title={hasArchivedSelected
                  ? undefined : 'Aucun lead archivé sélectionné'}>
          Restaurer
        </Button>
        <Button type="button" size="sm" variant="outline"
                onClick={onExport} disabled={busy}>
          <Download /> Exporter Excel
        </Button>
        {canDelete && (
          <Button type="button" size="sm" variant="destructive"
                  onClick={() => {
                    if (window.confirm(
                      `Supprimer définitivement ${count} lead(s) ? `
                      + 'Les leads avec des devis liés seront ignorés.')) {
                      run('delete')
                    }
                  }} disabled={busy}>
            Supprimer
          </Button>
        )}
        <Button type="button" size="sm" variant="ghost" className="bulk-bar-clear"
                onClick={onClear} disabled={busy}>
          <X /> Désélectionner
        </Button>
      </div>

      {panel === 'reassign' && (
        <div className="bulk-panel">
          <Select
            value={owner || NO_OWNER}
            onValueChange={(v) => setOwner(v === NO_OWNER ? '' : v)}
          >
            <SelectTrigger className="bulk-field"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_OWNER}>Aucun responsable</SelectItem>
              {users.map((u) => (
                <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="button" size="sm"
                  onClick={() => run('reassign', { owner: owner || null })}>
            Appliquer
          </Button>
        </div>
      )}

      {panel === 'stage' && (
        <div className="bulk-panel">
          <Select value={stage} onValueChange={setStage}>
            <SelectTrigger className="bulk-field"><SelectValue /></SelectTrigger>
            <SelectContent>
              {PIPELINE_STAGES.map((s) => (
                <SelectItem key={s} value={s}>{STAGE_LABELS[s] ?? s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="button" size="sm"
                  onClick={() => run('set_stage', { stage })}>
            Appliquer
          </Button>
          <span className="bulk-hint">
            Ne recule jamais une étape ; ignore les leads Perdu.
          </span>
        </div>
      )}

      {panel === 'canal' && (
        <div className="bulk-panel">
          <Select value={canal} onValueChange={setCanal}>
            <SelectTrigger className="bulk-field"><SelectValue /></SelectTrigger>
            <SelectContent>
              {Object.entries(CANAL_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="button" size="sm"
                  onClick={() => run('set_canal', { canal })}>
            Appliquer
          </Button>
        </div>
      )}

      {panel === 'priorite' && (
        <div className="bulk-panel">
          <Select value={priorite} onValueChange={setPriorite}>
            <SelectTrigger className="bulk-field"><SelectValue /></SelectTrigger>
            <SelectContent>
              {Object.entries(PRIORITE_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="button" size="sm"
                  onClick={() => run('set_priorite', { priorite })}>
            Appliquer
          </Button>
        </div>
      )}

      {panel === 'tag' && (
        <div className="bulk-panel">
          <Input className="bulk-field" placeholder="Étiquette"
                 value={tag} onChange={(e) => setTag(e.target.value)} />
          <Button type="button" size="sm"
                  disabled={!tag.trim()}
                  onClick={() => run('add_tag', { tag: tag.trim() })}>
            Ajouter
          </Button>
          <Button type="button" size="sm" variant="outline"
                  disabled={!tag.trim()}
                  onClick={() => run('remove_tag', { tag: tag.trim() })}>
            Retirer
          </Button>
        </div>
      )}

      {panel === 'relance' && (
        <div className="bulk-panel">
          <Input type="date" className="bulk-field"
                 value={relance} onChange={(e) => setRelance(e.target.value)} />
          <Button type="button" size="sm"
                  disabled={!relance}
                  onClick={() => run('set_relance', { relance_date: relance })}>
            Définir
          </Button>
          <Button type="button" size="sm" variant="outline"
                  onClick={() => run('clear_relance')}>
            Effacer la relance
          </Button>
        </div>
      )}

      {panel === 'activity' && (
        <div className="bulk-panel">
          <Input className="bulk-field" placeholder="Intitulé (ex. Appeler)"
                 value={actSummary} onChange={(e) => setActSummary(e.target.value)} />
          <Input type="date" className="bulk-field"
                 value={actDue} onChange={(e) => setActDue(e.target.value)} />
          <Button type="button" size="sm"
                  disabled={!actSummary.trim() || !actDue}
                  onClick={() => run('plan_activity', {
                    summary: actSummary.trim(), due_date: actDue,
                  })}>
            Planifier
          </Button>
          <span className="bulk-hint">
            Crée une activité ouverte sur chaque lead, assignée à son responsable.
          </span>
        </div>
      )}

      {panel === 'perdu' && (
        <div className="bulk-panel">
          <Input className="bulk-field" placeholder="Motif (optionnel)"
                 value={motif} onChange={(e) => setMotif(e.target.value)} />
          <Button type="button" size="sm"
                  onClick={() => run('set_perdu', { motif: motif.trim() })}>
            Marquer Perdu
          </Button>
          <Button type="button" size="sm" variant="outline"
                  onClick={() => run('unset_perdu')}>
            Annuler Perdu
          </Button>
        </div>
      )}
    </div>
  )
}
