// Checklist d'exécution d'un chantier (N3) : étapes cochables + barre
// d'avancement. Les étapes sont pré-remplies côté serveur depuis les défauts
// société ; cocher enregistre qui/quand et journalise dans l'Historique.
import { useEffect, useState } from 'react'
import installationsApi from '../../api/installationsApi'

const formatDateFr = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString('fr-FR')
}

export default function ChecklistPanel({ installationId, onChange }) {
  const [items, setItems] = useState([])
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    installationsApi.getChecklist(installationId)
      .then(r => setItems(r.data ?? [])).catch(() => {})
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = async (item) => {
    setBusyId(item.id)
    try {
      const r = await installationsApi.toggleChecklistItem(
        installationId, item.id, !item.done)
      setItems(cur => cur.map(it => (it.id === item.id ? r.data : it)))
      onChange?.()
    } catch { /* erreur silencieuse */ } finally { setBusyId(null) }
  }

  const total = items.length
  const done = items.filter(it => it.done).length
  const percent = total ? Math.round(done * 100 / total) : 0

  return (
    <div>
      <div className="cd-progress">
        <div className="cd-progress-bar">
          <div className="cd-progress-fill" style={{ width: `${percent}%` }} />
        </div>
        <div className="cd-progress-label">
          {done}/{total} étapes — {percent}%
        </div>
      </div>
      {items.length === 0 ? (
        <p className="gen-hint">Aucune étape.</p>
      ) : (
        <div className="cd-check-list">
          {items.map(item => (
            <label
              key={item.id}
              className={`cd-check-item${item.done ? ' cd-done' : ''}`}
            >
              <input
                type="checkbox"
                checked={item.done}
                disabled={busyId === item.id}
                onChange={() => toggle(item)}
              />
              <span className="cd-check-label">{item.label}</span>
              {item.done && (
                <span className="cd-check-meta">
                  {item.done_by_nom ? `${item.done_by_nom} · ` : ''}
                  {formatDateFr(item.done_at)}
                </span>
              )}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
