import { useCallback, useEffect, useState } from 'react'
import immobilierApi from '../../api/immobilierApi'

/* ============================================================================
   WIR147 — Écran Locataires (`/immobilier/locataires`).
   ----------------------------------------------------------------------------
   `LocataireViewSet` (CRUD + `resolve-client`) n'avait aucun écran alors que
   le wrapper `immobilierApi.locataires` existe déjà. Liste + création/édition
   + résolution manuelle du client ventes (crm.Client) quand elle n'a pas
   encore eu lieu (ex. locataire créé avant tout bail/facturation).
   ========================================================================== */

function rowsFrom(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

const FIELDS = [
  {
    key: 'type_locataire',
    label: 'Type',
    type: 'select',
    options: [
      { value: 'particulier', label: 'Particulier' },
      { value: 'societe', label: 'Société' },
    ],
  },
  { key: 'nom', label: 'Nom / raison sociale', required: true },
  { key: 'cin', label: 'CIN' },
  { key: 'ice', label: 'ICE' },
  { key: 'telephone', label: 'Téléphone' },
  { key: 'email', label: 'Email' },
  { key: 'adresse', label: 'Adresse' },
]

export default function LocatairesPage() {
  const [locataires, setLocataires] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState('create')
  const [formRowId, setFormRowId] = useState(null)
  const [formValues, setFormValues] = useState({})
  const [formErreur, setFormErreur] = useState(null)
  const [formSaving, setFormSaving] = useState(false)

  const [resolvingId, setResolvingId] = useState(null)

  const reload = useCallback(async () => {
    const res = await immobilierApi.locataires.list()
    setLocataires(rowsFrom(res.data))
  }, [])

  useEffect(() => {
    let annule = false
    immobilierApi.locataires
      .list()
      .then((res) => {
        if (!annule) setLocataires(rowsFrom(res.data))
      })
      .catch(() => {
        if (!annule) setErreur('Chargement des locataires impossible.')
      })
      .finally(() => {
        if (!annule) setLoading(false)
      })
    return () => {
      annule = true
    }
  }, [])

  const openCreateForm = useCallback(() => {
    const initial = {}
    FIELDS.forEach((f) => {
      initial[f.key] = f.type === 'select' ? (f.options?.[0]?.value ?? '') : ''
    })
    setFormValues(initial)
    setFormMode('create')
    setFormRowId(null)
    setFormErreur(null)
    setFormOpen(true)
  }, [])

  const openEditForm = useCallback((row) => {
    const initial = {}
    FIELDS.forEach((f) => {
      initial[f.key] = row[f.key] ?? ''
    })
    setFormValues(initial)
    setFormMode('edit')
    setFormRowId(row.id)
    setFormErreur(null)
    setFormOpen(true)
  }, [])

  const closeForm = useCallback(() => setFormOpen(false), [])

  const handleFormChange = useCallback((key, value) => {
    setFormValues((v) => ({ ...v, [key]: value }))
  }, [])

  const handleFormSubmit = useCallback(async (e) => {
    e.preventDefault()
    const payload = {}
    FIELDS.forEach((f) => {
      payload[f.key] = formValues[f.key] ?? ''
    })
    setFormSaving(true)
    setFormErreur(null)
    try {
      if (formMode === 'edit') {
        await immobilierApi.locataires.update(formRowId, payload)
      } else {
        await immobilierApi.locataires.create(payload)
      }
      await reload()
      setFormOpen(false)
    } catch {
      setFormErreur('Enregistrement impossible.')
    } finally {
      setFormSaving(false)
    }
  }, [formMode, formRowId, formValues, reload])

  const resoudreClient = useCallback(async (id) => {
    setResolvingId(id)
    setErreur(null)
    try {
      await immobilierApi.locataires.resolveClient(id)
      await reload()
    } catch {
      setErreur('Résolution du client ventes impossible.')
    } finally {
      setResolvingId(null)
    }
  }, [reload])

  return (
    <div data-testid="locataires-page" style={{ padding: 16 }}>
      <h1>Locataires</h1>

      {loading && <p>Chargement…</p>}
      {erreur && <p role="alert">{erreur}</p>}

      <button type="button" onClick={openCreateForm} style={{ marginBottom: 12 }}>
        Ajouter un locataire
      </button>

      {formOpen && (
        <form
          data-testid="form-locataire"
          onSubmit={handleFormSubmit}
          style={{ border: '1px solid var(--border, #ccc)', padding: 12, marginBottom: 16 }}
        >
          <h3>{formMode === 'edit' ? 'Modifier le locataire' : 'Nouveau locataire'}</h3>
          {FIELDS.map((f) => (
            <label key={f.key} style={{ display: 'block', marginBottom: 8 }}>
              {f.label}{' '}
              {f.type === 'select' ? (
                <select
                  aria-label={f.label}
                  value={formValues[f.key] ?? ''}
                  onChange={(e) => handleFormChange(f.key, e.target.value)}
                >
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  aria-label={f.label}
                  required={!!f.required}
                  value={formValues[f.key] ?? ''}
                  onChange={(e) => handleFormChange(f.key, e.target.value)}
                />
              )}
            </label>
          ))}
          {formErreur && <p role="alert">{formErreur}</p>}
          <button type="submit" disabled={formSaving}>
            {formMode === 'edit' ? 'Enregistrer' : 'Créer'}
          </button>{' '}
          <button type="button" onClick={closeForm} disabled={formSaving}>
            Annuler
          </button>
        </form>
      )}

      <table data-testid="table-locataires">
        <thead>
          <tr>
            <th>Nom</th>
            <th>Type</th>
            <th>Téléphone</th>
            <th>Email</th>
            <th>Client ventes</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {locataires.map((row) => (
            <tr key={row.id}>
              <td>{row.nom}</td>
              <td>{row.type_locataire_display || row.type_locataire}</td>
              <td>{row.telephone}</td>
              <td>{row.email}</td>
              <td>{row.client_ventes_id ? 'Résolu' : 'Non résolu'}</td>
              <td>
                <button type="button" onClick={() => openEditForm(row)}>Modifier</button>
                {' '}
                {!row.client_ventes_id && (
                  <button
                    type="button"
                    onClick={() => resoudreClient(row.id)}
                    disabled={resolvingId === row.id}
                  >
                    Résoudre client
                  </button>
                )}
              </td>
            </tr>
          ))}
          {locataires.length === 0 && !loading && (
            <tr><td colSpan={6}>Aucun locataire.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
