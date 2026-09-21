import { useEffect, useState } from 'react'

import creditApi from '../../api/creditApi'

/* ============================================================================
   NTCRD15 — Écran « Conditions de paiement par segment » (CRUD simple :
   liste / ajout / édition). Destiné à l'onglet Ventes des Paramètres, réservé
   Directeur/Administrateur (le backend re-vérifie : IsDirecteurOrAdmin).
   Créer/modifier une condition se reflète immédiatement dans le résolveur
   NTCRD13 pour le prochain devis d'un client de ce segment.
   ========================================================================== */

const EMPTY = {
  segment: '',
  delai_paiement_jours: 0,
  pct_acompte_defaut: '',
  mode_hold_override: '',
}

export default function ConditionsSegmentScreen() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState(null)

  function reload() {
    creditApi
      .getConditionsSegment()
      .then((res) => setRows(res.data.results || res.data))
      .catch(() => setError('Chargement impossible.'))
  }

  useEffect(reload, [])

  function edit(row) {
    setEditingId(row.id)
    setForm({
      segment: row.segment,
      delai_paiement_jours: row.delai_paiement_jours,
      pct_acompte_defaut: row.pct_acompte_defaut ?? '',
      mode_hold_override: row.mode_hold_override || '',
    })
  }

  async function save(e) {
    e.preventDefault()
    setError(null)
    const payload = {
      ...form,
      pct_acompte_defaut: form.pct_acompte_defaut === '' ? null : form.pct_acompte_defaut,
    }
    try {
      if (editingId) await creditApi.updateConditionSegment(editingId, payload)
      else await creditApi.createConditionSegment(payload)
      setForm(EMPTY)
      setEditingId(null)
      reload()
    } catch {
      setError('Enregistrement impossible.')
    }
  }

  return (
    <div className="credit-conditions" data-testid="credit-conditions-segment">
      <h3>Conditions de paiement par segment</h3>
      {error && <p className="credit-conditions__error">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Segment</th>
            <th>Délai (j)</th>
            <th>Acompte %</th>
            <th>Hold override</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.segment}</td>
              <td>{row.delai_paiement_jours}</td>
              <td>{row.pct_acompte_defaut ?? '—'}</td>
              <td>{row.mode_hold_override || '—'}</td>
              <td>
                <button type="button" onClick={() => edit(row)}>
                  Éditer
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form onSubmit={save} className="credit-conditions__form">
        <input
          placeholder="Segment"
          value={form.segment}
          onChange={(e) => setForm({ ...form, segment: e.target.value })}
          required
        />
        <input
          type="number"
          placeholder="Délai (j)"
          value={form.delai_paiement_jours}
          onChange={(e) =>
            setForm({ ...form, delai_paiement_jours: e.target.value })
          }
        />
        <input
          type="number"
          step="any"
          placeholder="Acompte %"
          value={form.pct_acompte_defaut}
          onChange={(e) =>
            setForm({ ...form, pct_acompte_defaut: e.target.value })
          }
        />
        <select
          value={form.mode_hold_override}
          onChange={(e) =>
            setForm({ ...form, mode_hold_override: e.target.value })
          }
        >
          <option value="">(défaut société)</option>
          <option value="aucun">Aucun</option>
          <option value="avertissement">Avertissement</option>
          <option value="blocage">Blocage</option>
        </select>
        <button type="submit">{editingId ? 'Mettre à jour' : 'Ajouter'}</button>
      </form>
    </div>
  )
}
