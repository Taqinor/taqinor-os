/* Sélecteur de responsable façon Odoo : pastille avatar + nom, ouvre une liste
   d'employés avec leurs avatars. Réutilisé dans la fiche lead et sur la carte
   kanban. Reçoit la liste des employés (assignables) en prop pour éviter de
   refetcher par carte. */
import { useEffect, useRef, useState } from 'react'
import Avatar from './Avatar'

export default function AssigneePicker({
  users = [],
  value,                // id du responsable courant (ou '' / null)
  onChange,             // (id|null) => void
  size = 24,
  disabled = false,
  allowUnassigned = true,
  compact = false,      // true = bouton pastille seule (carte kanban)
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const current = users.find(u => String(u.id) === String(value)) || null
  const currentName = current?.username || null

  const pick = (id) => {
    setOpen(false)
    if (String(id ?? '') !== String(value ?? '')) onChange?.(id)
  }

  return (
    <div className={`ap-wrap${compact ? ' ap-compact' : ''}`} ref={ref}>
      <button
        type="button"
        className="ap-trigger"
        disabled={disabled}
        title={currentName ? `Responsable : ${currentName}` : 'Assigner un responsable'}
        onClick={(e) => { e.stopPropagation(); if (!disabled) setOpen(o => !o) }}
      >
        <Avatar name={currentName} src={current?.avatar_url} size={size} />
        {!compact && <span className="ap-name">{currentName || 'Non assigné'}</span>}
      </button>

      {open && (
        <div className="ap-menu" onClick={(e) => e.stopPropagation()}>
          {allowUnassigned && (
            <button type="button" className="ap-item" onClick={() => pick(null)}>
              <Avatar name={null} size={22} />
              <span className="ap-item-name">Non assigné</span>
            </button>
          )}
          {users.map(u => (
            <button key={u.id} type="button" className="ap-item" onClick={() => pick(u.id)}>
              <Avatar name={u.username} src={u.avatar_url} size={22} />
              <span className="ap-item-name">
                {u.username}
                {u.poste && <span className="ap-item-poste">{u.poste}</span>}
              </span>
            </button>
          ))}
          {users.length === 0 && (
            <div className="ap-empty">Aucun employé disponible</div>
          )}
        </div>
      )}
    </div>
  )
}
