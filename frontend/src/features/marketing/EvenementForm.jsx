/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState } from 'react'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT7 — Formulaire de création/édition d'un événement marketing (XMKT28).
   ----------------------------------------------------------------------------
   Type (salon/porte ouverte/webinaire), dates, lieu/lien visio, capacité.
   Les billets (ZMKT15, `BilletEvenement`) se gèrent depuis `EvenementDetail.jsx`
   (ont besoin d'un `evenement.id` existant) — pas dupliqués ici.

   WIR162 — sélecteur de modèle réutilisable (ZMKT14, `TypeEvenement`) : à la
   CRÉATION uniquement (`!editing`), choisir un modèle recopie sa config par
   défaut (`type_evenement`) et garde la trace de la source (`type_modele`)
   côté serveur via l'action dédiée `types-evenement/<id>/creer-evenement/`
   (`typesEvenement.creerEvenement`, marketingApi.js) — le parent (`onSave`)
   décide de router vers cette action plutôt que le POST générique quand un
   modèle est choisi.
   ========================================================================== */

const TYPES = [
  { key: 'salon', label: 'Salon' },
  { key: 'porte_ouverte', label: 'Porte ouverte' },
  { key: 'webinaire', label: 'Webinaire' },
]

export function emptyForm() {
  return { nom: '', type_evenement: 'salon', date_debut: '', date_fin: '', lieu: '', capacite: '', type_modele: '' }
}

export function formFromEvenement(ev) {
  return {
    nom: ev.nom || '', type_evenement: ev.type_evenement || 'salon',
    date_debut: ev.date_debut ? ev.date_debut.slice(0, 16) : '',
    date_fin: ev.date_fin ? ev.date_fin.slice(0, 16) : '',
    lieu: ev.lieu || '', capacite: ev.capacite ?? '',
    type_modele: ev.type_modele ?? '',
  }
}

export default function EvenementForm({ initial, onSave, onCancel, editing }) {
  const [form, setForm] = useState(initial || emptyForm())
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)
  // WIR162 — modèles disponibles pour le sélecteur (création uniquement).
  const [modeles, setModeles] = useState([])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- resync le formulaire quand la prop initial change
  useEffect(() => { setForm(initial || emptyForm()) }, [initial])

  useEffect(() => {
    if (editing) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    marketingApi.typesEvenement.list()
      .then(r => setModeles(marketingApi.unwrapList(r)))
      .catch(() => setModeles([]))
  }, [editing])

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
        type_modele: form.type_modele === '' ? null : Number(form.type_modele),
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
      {/* WIR162 — sélecteur de modèle réutilisable (ZMKT14), création uniquement. */}
      {!editing && modeles.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <label htmlFor="evenement-type-modele" style={{ fontSize: '0.85rem', color: '#475569' }}>
            Créer depuis un modèle (optionnel)
          </label>
          <select id="evenement-type-modele" className="form-input" data-testid="evenement-type-modele"
            value={form.type_modele} onChange={setField('type_modele')} style={{ flex: '1 1 200px' }}>
            <option value="">Aucun modèle</option>
            {modeles.map(m => <option key={m.id} value={m.id}>{m.nom}</option>)}
          </select>
        </div>
      )}
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
