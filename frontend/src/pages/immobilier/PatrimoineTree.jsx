import { useCallback, useEffect, useMemo, useState } from 'react'
import immobilierApi from '../../api/immobilierApi'

/* ============================================================================
   NTPRO1 — Arborescence du patrimoine (`/immobilier`).
   ----------------------------------------------------------------------------
   Navigation Site → Bâtiment → Niveau → Local avec fil d'Ariane cliquable :
   un local est localisable en 4 clics depuis la racine (clic 1 = site, clic 2
   = bâtiment, clic 3 = niveau, clic 4 = local). Chaque niveau de la hiérarchie
   n'appelle que l'endpoint filtré correspondant (jamais de sur-lecture).

   WIR147 — CRUD : les 4 ViewSets + wrappers `immobilierApi.js` supportent déjà
   POST/PATCH ; un formulaire « Ajouter/Modifier » générique (piloté par
   `LEVEL_CONFIG`) s'ouvre au niveau courant de l'arborescence, sans écran
   dédié par niveau (évite 4 pages quasi identiques).
   ========================================================================== */

function rowsFrom(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

const LEVELS = ['site', 'batiment', 'niveau', 'local']

const TYPE_LOCAL_OPTIONS = [
  { value: 'habitation', label: 'Habitation' },
  { value: 'commerce', label: 'Commerce' },
  { value: 'bureau', label: 'Bureau' },
  { value: 'parking', label: 'Parking' },
  { value: 'entrepot', label: 'Entrepôt' },
]

// Un niveau par clé de LEVELS ci-dessus : `api` = wrapper CRUD immobilierApi,
// `fields` = formulaire (ordre d'affichage), `parentField` = nom du champ FK
// posé automatiquement depuis le parent sélectionné dans l'arborescence.
const LEVEL_CONFIG = {
  site: {
    label: 'un site',
    api: immobilierApi.sites,
    fields: [
      { key: 'nom', label: 'Nom', required: true },
      { key: 'adresse', label: 'Adresse' },
      { key: 'ville', label: 'Ville' },
    ],
  },
  batiment: {
    label: 'un bâtiment',
    api: immobilierApi.batiments,
    parentField: 'site',
    fields: [
      { key: 'nom', label: 'Nom', required: true },
      { key: 'nb_niveaux', label: 'Nombre de niveaux', type: 'number' },
      { key: 'annee_construction', label: 'Année de construction', type: 'number' },
    ],
  },
  niveau: {
    label: 'un niveau',
    api: immobilierApi.niveaux,
    parentField: 'batiment',
    fields: [
      { key: 'numero', label: 'Numéro / libellé', required: true },
      { key: 'ordre', label: "Ordre d'affichage", type: 'number' },
    ],
  },
  local: {
    label: 'un local',
    api: immobilierApi.locaux,
    parentField: 'niveau',
    fields: [
      { key: 'reference', label: 'Référence', required: true },
      { key: 'type_local', label: 'Type', type: 'select', options: TYPE_LOCAL_OPTIONS },
      { key: 'surface_m2', label: 'Surface (m²)', type: 'number' },
      { key: 'tantiemes', label: 'Tantièmes', type: 'number' },
    ],
  },
}

export default function PatrimoineTree() {
  const [site, setSite] = useState(null)
  const [batiment, setBatiment] = useState(null)
  const [niveau, setNiveau] = useState(null)

  const [sites, setSites] = useState([])
  const [batiments, setBatiments] = useState([])
  const [niveaux, setNiveaux] = useState([])
  const [locaux, setLocaux] = useState([])
  // Chargée dès le montage (l'effet ci-dessous lance la requête sites sans
  // condition) : l'état initial porte déjà `true`/`null`, ce qui évite tout
  // setState synchrone au premier rendu de l'effet (react-hooks/set-state-in-effect).
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  // WIR147 — état du formulaire CRUD générique (un seul formulaire, piloté
  // par le niveau courant de l'arborescence).
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState('create')
  const [formRowId, setFormRowId] = useState(null)
  const [formValues, setFormValues] = useState({})
  const [formErreur, setFormErreur] = useState(null)
  const [formSaving, setFormSaving] = useState(false)

  useEffect(() => {
    let annule = false
    immobilierApi.sites
      .list()
      .then((res) => {
        if (!annule) setSites(rowsFrom(res.data))
      })
      .catch(() => {
        if (!annule) setErreur('Chargement des sites impossible.')
      })
      .finally(() => {
        if (!annule) setLoading(false)
      })
    return () => {
      annule = true
    }
  }, [])

  useEffect(() => {
    // Pas de reset synchrone vers [] ici (react-hooks/set-state-in-effect) :
    // `batiments` n'est de toute façon jamais lu par le rendu tant que `site`
    // est vide (cf. `currentRows` plus bas), le early-return suffit.
    if (!site) return undefined
    let annule = false
    immobilierApi.batiments.list({ site: site.id }).then((res) => {
      if (!annule) setBatiments(rowsFrom(res.data))
    })
    return () => {
      annule = true
    }
  }, [site])

  useEffect(() => {
    // Idem : `niveaux` n'est jamais lu par le rendu tant que `batiment` est vide.
    if (!batiment) return undefined
    let annule = false
    immobilierApi.niveaux.list({ batiment: batiment.id }).then((res) => {
      if (!annule) setNiveaux(rowsFrom(res.data))
    })
    return () => {
      annule = true
    }
  }, [batiment])

  useEffect(() => {
    // Idem : `locaux` n'est jamais lu par le rendu tant que `niveau` est vide.
    if (!niveau) return undefined
    let annule = false
    immobilierApi.locaux.list({ niveau: niveau.id }).then((res) => {
      if (!annule) setLocaux(rowsFrom(res.data))
    })
    return () => {
      annule = true
    }
  }, [niveau])

  const breadcrumb = useMemo(() => {
    const parts = [{ label: 'Patrimoine', onClick: () => goToRacine() }]
    if (site) parts.push({ label: site.nom, onClick: () => goToSite(site) })
    if (batiment) parts.push({ label: batiment.nom, onClick: () => goToBatiment(batiment) })
    if (niveau) parts.push({ label: niveau.numero, onClick: () => goToNiveau(niveau) })
    return parts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [site, batiment, niveau])

  const goToRacine = useCallback(() => {
    setSite(null)
    setBatiment(null)
    setNiveau(null)
  }, [])
  const goToSite = useCallback((s) => {
    setSite(s)
    setBatiment(null)
    setNiveau(null)
  }, [])
  const goToBatiment = useCallback((b) => {
    setBatiment(b)
    setNiveau(null)
  }, [])
  const goToNiveau = useCallback((n) => {
    setNiveau(n)
  }, [])

  let currentLevel = 'site'
  let currentRows = sites
  let currentLabel = 'Sites'
  let onSelect = goToSite
  if (site && !batiment) {
    currentLevel = 'batiment'
    currentRows = batiments
    currentLabel = 'Bâtiments'
    onSelect = goToBatiment
  } else if (batiment && !niveau) {
    currentLevel = 'niveau'
    currentRows = niveaux
    currentLabel = 'Niveaux'
    onSelect = goToNiveau
  } else if (niveau) {
    currentLevel = 'local'
    currentRows = locaux
    currentLabel = 'Locaux'
    onSelect = null
  }

  // Parent sélectionné pour chaque niveau, indexé par le nom du champ FK
  // (`LEVEL_CONFIG[level].parentField`) — permet de poser automatiquement
  // `payload[parentField] = PARENTS[parentField].id` sans switch dupliqué.
  const PARENTS = { site, batiment, niveau }

  // Fonctions simples (pas de `useCallback`) : elles sont clefées sur
  // `currentLevel`, une variable LOCALE recalculée à chaque rendu — la
  // mémoïsation manuelle n'apportait rien et empêchait le compilateur React de
  // la préserver (react-hooks/preserve-manual-memoization). Aucune n'est
  // utilisée comme dépendance : appelées uniquement depuis des gestionnaires.
  const reloadCurrentLevel = async () => {
    if (currentLevel === 'site') {
      const res = await immobilierApi.sites.list()
      setSites(rowsFrom(res.data))
    } else if (currentLevel === 'batiment') {
      const res = await immobilierApi.batiments.list({ site: site.id })
      setBatiments(rowsFrom(res.data))
    } else if (currentLevel === 'niveau') {
      const res = await immobilierApi.niveaux.list({ batiment: batiment.id })
      setNiveaux(rowsFrom(res.data))
    } else if (currentLevel === 'local') {
      const res = await immobilierApi.locaux.list({ niveau: niveau.id })
      setLocaux(rowsFrom(res.data))
    }
  }

  const openCreateForm = () => {
    const config = LEVEL_CONFIG[currentLevel]
    const initial = {}
    config.fields.forEach((f) => {
      initial[f.key] = f.type === 'select' ? (f.options?.[0]?.value ?? '') : ''
    })
    setFormValues(initial)
    setFormMode('create')
    setFormRowId(null)
    setFormErreur(null)
    setFormOpen(true)
  }

  const openEditForm = (row) => {
    const config = LEVEL_CONFIG[currentLevel]
    const initial = {}
    config.fields.forEach((f) => {
      initial[f.key] = row[f.key] ?? ''
    })
    setFormValues(initial)
    setFormMode('edit')
    setFormRowId(row.id)
    setFormErreur(null)
    setFormOpen(true)
  }

  const closeForm = useCallback(() => setFormOpen(false), [])

  const handleFormChange = useCallback((key, value) => {
    setFormValues((v) => ({ ...v, [key]: value }))
  }, [])

  const handleFormSubmit = useCallback(async (e) => {
    e.preventDefault()
    const config = LEVEL_CONFIG[currentLevel]
    const payload = {}
    config.fields.forEach((f) => {
      const v = formValues[f.key]
      payload[f.key] = f.type === 'number'
        ? (v === '' || v === undefined ? null : Number(v))
        : (v ?? '')
    })
    if (config.parentField) {
      payload[config.parentField] = PARENTS[config.parentField]?.id
    }
    setFormSaving(true)
    setFormErreur(null)
    try {
      if (formMode === 'edit') {
        await config.api.update(formRowId, payload)
      } else {
        await config.api.create(payload)
      }
      await reloadCurrentLevel()
      setFormOpen(false)
    } catch {
      setFormErreur('Enregistrement impossible.')
    } finally {
      setFormSaving(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentLevel, formMode, formRowId, formValues, PARENTS.site, PARENTS.batiment, PARENTS.niveau])

  const levelConfig = LEVEL_CONFIG[currentLevel]

  return (
    <div data-testid="patrimoine-tree" style={{ padding: 16 }}>
      <h1>Patrimoine</h1>
      <nav aria-label="Fil d'Ariane" style={{ marginBottom: 12 }}>
        {breadcrumb.map((part, idx) => (
          <span key={part.label}>
            {idx > 0 && ' / '}
            <button type="button" onClick={part.onClick}>
              {part.label}
            </button>
          </span>
        ))}
      </nav>

      {loading && <p>Chargement…</p>}
      {erreur && <p role="alert">{erreur}</p>}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>{currentLabel}</h2>
        <button type="button" onClick={openCreateForm}>
          Ajouter {levelConfig.label}
        </button>
      </div>

      {formOpen && (
        <form
          data-testid="form-patrimoine"
          onSubmit={handleFormSubmit}
          style={{ border: '1px solid var(--border, #ccc)', padding: 12, marginBottom: 16 }}
        >
          <h3>
            {formMode === 'edit' ? `Modifier ${levelConfig.label}` : `Ajouter ${levelConfig.label}`}
          </h3>
          {levelConfig.fields.map((f) => (
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
                  type={f.type === 'number' ? 'number' : 'text'}
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

      <ul data-testid={`niveau-${currentLevel}`}>
        {currentRows.map((row) => (
          <li key={row.id}>
            {onSelect ? (
              <button type="button" onClick={() => onSelect(row)}>
                {row.nom || row.numero || row.reference}
              </button>
            ) : (
              <span>
                {row.reference} — {row.type_local_display || row.type_local} —{' '}
                {row.statut_display || row.statut}
              </span>
            )}
            {' '}
            <button type="button" onClick={() => openEditForm(row)}>Modifier</button>
          </li>
        ))}
        {currentRows.length === 0 && !loading && <li>Aucun élément.</li>}
      </ul>
    </div>
  )
}

// Réexport pour les tests (LEVELS documente l'ordre de la hiérarchie).
export { LEVELS, LEVEL_CONFIG }
