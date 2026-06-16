// Barre d'actions « en masse » (T3) — affichée dès qu'au moins un lead est
// sélectionné dans la liste ou le kanban. Toutes les actions passent par
// l'endpoint serveur /crm/leads/bulk/ (journal « en masse » côté serveur).
import { useState } from 'react'
import { useSelector } from 'react-redux'
import crmApi from '../../../api/crmApi'
import {
  PIPELINE_STAGES,
  STAGE_LABELS,
} from '../../../features/crm/stages'
import AssigneePicker from '../../../components/AssigneePicker'
import './bulktoolbar.css'

// Petit menu déroulant générique (réutilisé pour étape / tags / relance…).
function Dropdown({ label, children, busy }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="bt-dd">
      <button
        type="button"
        className="btn btn-sm btn-outline"
        disabled={busy}
        onClick={() => setOpen((o) => !o)}
      >
        {label} ▾
      </button>
      {open && (
        <div className="bt-dd-menu" onMouseLeave={() => setOpen(false)}>
          {typeof children === 'function' ? children(() => setOpen(false)) : children}
        </div>
      )}
    </div>
  )
}

export default function BulkToolbar({
  selectedIds,
  onClear,
  onDone,
  users = [],
}) {
  const role = useSelector((s) => s.auth.role)
  const canDelete = role === 'admin'
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const count = selectedIds.length
  if (!count) return null

  const run = async (action, params = {}) => {
    setBusy(true)
    setMsg(null)
    try {
      const r = await crmApi.bulkLeads(action, selectedIds, params)
      const d = r.data || {}
      if (typeof d.updated === 'number') {
        let txt = `${d.updated} lead(s) mis à jour`
        if (d.skipped) txt += `, ${d.skipped} ignoré(s)`
        setMsg(txt)
      } else if (typeof d.deleted === 'number') {
        setMsg(`${d.deleted} lead(s) supprimé(s)`)
      }
      onDone?.()
    } catch (err) {
      setMsg(err?.response?.data?.detail ?? 'Action impossible.')
    } finally {
      setBusy(false)
    }
  }

  const onExport = async () => {
    setBusy(true)
    setMsg(null)
    try {
      const r = await crmApi.exportLeads(selectedIds)
      const url = window.URL.createObjectURL(new Blob([r.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'leads.xlsx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      setMsg('Export impossible.')
    } finally {
      setBusy(false)
    }
  }

  const onDelete = async () => {
    if (!window.confirm(
      `Supprimer définitivement ${count} lead(s) ? Action irréversible.`)) return
    await run('delete')
  }

  const askTag = (action) => {
    const tag = window.prompt(
      action === 'add_tag' ? 'Tag à ajouter :' : 'Tag à retirer :')
    if (tag && tag.trim()) run(action, { tag: tag.trim() })
  }

  const askMotif = () => {
    const motif = window.prompt('Motif de perte (optionnel) :') ?? ''
    run('flag_perdu', { motif_perte: motif.trim() })
  }

  return (
    <div className="bt-bar" role="region" aria-label="Actions en masse">
      <div className="bt-count">
        <strong>{count}</strong> sélectionné{count > 1 ? 's' : ''}
        <button type="button" className="bt-clear" onClick={onClear}>
          Tout désélectionner
        </button>
      </div>

      <div className="bt-actions">
        <Dropdown label="Responsable" busy={busy}>
          <div className="bt-dd-pad">
            <AssigneePicker
              users={users}
              value=""
              onChange={(id) => run('reassign', { owner: id })}
              size={22}
            />
          </div>
        </Dropdown>

        <Dropdown label="Étape" busy={busy}>
          {(close) => PIPELINE_STAGES.map((s) => (
            <button
              key={s}
              type="button"
              className="bt-dd-item"
              onClick={() => { close(); run('change_stage', { stage: s }) }}
            >
              {STAGE_LABELS[s]}
            </button>
          ))}
        </Dropdown>

        <Dropdown label="Tags" busy={busy}>
          {(close) => (
            <>
              <button type="button" className="bt-dd-item"
                onClick={() => { close(); askTag('add_tag') }}>
                Ajouter un tag
              </button>
              <button type="button" className="bt-dd-item"
                onClick={() => { close(); askTag('remove_tag') }}>
                Retirer un tag
              </button>
            </>
          )}
        </Dropdown>

        <Dropdown label="Relance" busy={busy}>
          {(close) => (
            <div className="bt-dd-pad">
              <input
                type="date"
                className="search-input"
                onChange={(e) => {
                  if (e.target.value) {
                    close()
                    run('set_relance', { relance_date: e.target.value })
                  }
                }}
              />
              <button type="button" className="bt-dd-item"
                onClick={() => { close(); run('clear_relance') }}>
                Effacer la relance
              </button>
            </div>
          )}
        </Dropdown>

        <Dropdown label="Perdu" busy={busy}>
          {(close) => (
            <>
              <button type="button" className="bt-dd-item"
                onClick={() => { close(); askMotif() }}>
                Marquer perdu…
              </button>
              <button type="button" className="bt-dd-item"
                onClick={() => { close(); run('unflag_perdu') }}>
                Retirer « perdu »
              </button>
            </>
          )}
        </Dropdown>

        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
          onClick={() => run('archive')}>
          Archiver
        </button>
        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
          onClick={() => run('unarchive')}>
          Restaurer
        </button>
        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
          onClick={onExport}>
          Exporter .xlsx
        </button>
        {canDelete && (
          <button type="button" className="btn btn-sm btn-danger" disabled={busy}
            onClick={onDelete}>
            Supprimer
          </button>
        )}
      </div>

      {msg && <span className="bt-msg" role="status">{msg}</span>}
    </div>
  )
}
