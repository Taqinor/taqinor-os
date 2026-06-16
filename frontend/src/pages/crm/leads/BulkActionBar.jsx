// Barre d'actions EN MASSE (T3) — visible dès qu'au moins un lead est coché,
// partagée par la vue liste et la vue kanban. Chaque action ouvre un petit
// contrôle en ligne puis applique via onAction(action, params) (le parent
// appelle l'API et journalise « en masse » côté serveur). L'export passe par
// onExport. Les règles du funnel sont appliquées SERVEUR — ici, on ne fait que
// présenter les actions.
import { useState } from 'react'
import {
  PIPELINE_STAGES, STAGE_LABELS,
} from '../../../features/crm/stages'
import './bulkactionbar.css'

export default function BulkActionBar({
  count, users = [], canDelete, busy, onAction, onExport, onClear,
}) {
  // panneau ouvert ('reassign' | 'stage' | 'tag' | 'relance' | 'perdu' | null)
  const [panel, setPanel] = useState(null)
  const [owner, setOwner] = useState('')
  const [stage, setStage] = useState(PIPELINE_STAGES[0])
  const [tag, setTag] = useState('')
  const [relance, setRelance] = useState('')
  const [motif, setMotif] = useState('')

  const toggle = (name) => setPanel((p) => (p === name ? null : name))
  const run = (action, params) => { onAction(action, params); setPanel(null) }

  return (
    <div className="bulk-bar" role="region" aria-label="Actions en masse">
      <div className="bulk-bar-count">
        <strong>{count}</strong> sélectionné{count > 1 ? 's' : ''}
      </div>

      <div className="bulk-bar-actions">
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => toggle('reassign')} disabled={busy}>
          Responsable
        </button>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => toggle('stage')} disabled={busy}>
          Étape
        </button>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => toggle('tag')} disabled={busy}>
          Tag
        </button>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => toggle('relance')} disabled={busy}>
          Relance
        </button>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => toggle('perdu')} disabled={busy}>
          Perdu
        </button>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => run('archive')} disabled={busy}>
          Archiver
        </button>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => run('unarchive')} disabled={busy}>
          Restaurer
        </button>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={onExport} disabled={busy}>
          ⬇ Exporter Excel
        </button>
        {canDelete && (
          <button type="button" className="btn btn-sm btn-danger"
                  onClick={() => {
                    if (window.confirm(
                      `Supprimer définitivement ${count} lead(s) ? `
                      + 'Les leads avec des devis liés seront ignorés.')) {
                      run('delete')
                    }
                  }} disabled={busy}>
            Supprimer
          </button>
        )}
        <button type="button" className="btn btn-sm bulk-bar-clear"
                onClick={onClear} disabled={busy}>
          ✕ Désélectionner
        </button>
      </div>

      {panel === 'reassign' && (
        <div className="bulk-panel">
          <select className="form-control" value={owner}
                  onChange={(e) => setOwner(e.target.value)}>
            <option value="">Aucun responsable</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.username}</option>
            ))}
          </select>
          <button type="button" className="btn btn-sm btn-primary"
                  onClick={() => run('reassign', { owner: owner || null })}>
            Appliquer
          </button>
        </div>
      )}

      {panel === 'stage' && (
        <div className="bulk-panel">
          <select className="form-control" value={stage}
                  onChange={(e) => setStage(e.target.value)}>
            {PIPELINE_STAGES.map((s) => (
              <option key={s} value={s}>{STAGE_LABELS[s] ?? s}</option>
            ))}
          </select>
          <button type="button" className="btn btn-sm btn-primary"
                  onClick={() => run('set_stage', { stage })}>
            Appliquer
          </button>
          <span className="bulk-hint">
            Ne recule jamais une étape ; ignore les leads Perdu.
          </span>
        </div>
      )}

      {panel === 'tag' && (
        <div className="bulk-panel">
          <input className="form-control" placeholder="Étiquette"
                 value={tag} onChange={(e) => setTag(e.target.value)} />
          <button type="button" className="btn btn-sm btn-primary"
                  disabled={!tag.trim()}
                  onClick={() => run('add_tag', { tag: tag.trim() })}>
            Ajouter
          </button>
          <button type="button" className="btn btn-sm btn-outline"
                  disabled={!tag.trim()}
                  onClick={() => run('remove_tag', { tag: tag.trim() })}>
            Retirer
          </button>
        </div>
      )}

      {panel === 'relance' && (
        <div className="bulk-panel">
          <input type="date" className="form-control"
                 value={relance} onChange={(e) => setRelance(e.target.value)} />
          <button type="button" className="btn btn-sm btn-primary"
                  disabled={!relance}
                  onClick={() => run('set_relance', { relance_date: relance })}>
            Définir
          </button>
          <button type="button" className="btn btn-sm btn-outline"
                  onClick={() => run('clear_relance')}>
            Effacer la relance
          </button>
        </div>
      )}

      {panel === 'perdu' && (
        <div className="bulk-panel">
          <input className="form-control" placeholder="Motif (optionnel)"
                 value={motif} onChange={(e) => setMotif(e.target.value)} />
          <button type="button" className="btn btn-sm btn-primary"
                  onClick={() => run('set_perdu', { motif: motif.trim() })}>
            Marquer Perdu
          </button>
          <button type="button" className="btn btn-sm btn-outline"
                  onClick={() => run('unset_perdu')}>
            Annuler Perdu
          </button>
        </div>
      )}
    </div>
  )
}
