/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState } from 'react'

/* ============================================================================
   NTMKT7 — Formulaire de création/édition d'un événement marketing (XMKT28).
   ----------------------------------------------------------------------------
   Type (salon/porte ouverte/webinaire), dates, lieu/lien visio, capacité.
   Les billets (ZMKT15, `BilletEvenement`) se gèrent depuis `EvenementDetail.jsx`
   (ont besoin d'un `evenement.id` existant) — pas dupliqués ici.
   ========================================================================== */

const TYPES = [
  { key: 'salon', label: 'Salon' },
  { key: 'porte_ouverte', label: 'Porte ouverte' },
  { key: 'webinaire', label: 'Webinaire' },
]

export function emptyForm() {
  return { nom: '', type_evenement: 'salon', date_debut: '', date_fin: '', lieu: '', capacite: '' }
}

export function formFromEvenement(ev) {
  return {
    nom: ev.nom || '', type_evenement: ev.type_evenement || 'salon',
    date_debut: ev.date_debut ? ev.date_debut.slice(0, 16) : '',
    date_fin: ev.date_fin ? ev.date_fin.slice(0, 16) : '',
    lieu: ev.lieu || '', capacite: ev.capacite ?? '',
  }
}

export default function EvenementForm({ initial, onSave, onCancel, editing }) {
  const [form, setForm] = useState(initial || emptyForm())
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)

  // eslint-disable-next-line react-hooks/set-state-in-effect -- resync le formulaire quand la prop initial change
  useEffect(() => { setForm(initial || emptyForm()) }, [initial])

  const setField = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    setSaving(true)
    try {
      await onSave({
        ...form,
        date_debut: form.date_debut ? new Date(form.date_debut).toISOString() : null,
        date_fin: form.date_fin ? new Date(form.date_fin).toISOString() : null,
        capacite: form.capacite === '' ? null : Number(form.capacite),
      })
    } catch {
      setErr('Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="evenement-form"
      style={{ display: 'grid', gap: '0.5rem', maxWidth: 640 }}>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <input className="form-input" data-testid="evenement-nom" placeholder="Nom"
          required value={form.nom} onChange={setField('nom')} style={{ flex: '2 1 220px' }} />
        <select className="form-input" data-testid="evenement-type"
          value={form.type_evenement} onChange={setField('type_evenement')}
          style={{ flex: '1 1 160px' }}>
          {TYPES.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
        </select>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <input type="datetime-local" className="form-input" data-testid="evenement-date-debut"
          required value={form.date_debut} onChange={setField('date_debut')}
          style={{ flex: '1 1 200px' }} />
        <input type="datetime-local" className="form-input" data-testid="evenement-date-fin"
          value={form.date_fin} onChange={setField('date_fin')} style={{ flex: '1 1 200px' }} />
      </div>
      <input className="form-input" data-testid="evenement-lieu"
        placeholder="Lieu (ou lien visio)" value={form.lieu} onChange={setField('lieu')} />
      <input type="number" min={0} className="form-input" data-testid="evenement-capacite"
        placeholder="Capacité" value={form.capacite} onChange={setField('capacite')}
        style={{ maxWidth: 160 }} />
      {err && <p style={{ color: '#dc2626', margin: 0 }}>{err}</p>}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button type="submit" className="btn btn-primary" data-testid="evenement-save"
          disabled={saving}>
          {editing ? 'Enregistrer' : "Créer l'événement"}
        </button>
        {onCancel && (
          <button type="button" className="btn btn-light" onClick={onCancel}>Annuler</button>
        )}
      </div>
    </form>
  )
}
