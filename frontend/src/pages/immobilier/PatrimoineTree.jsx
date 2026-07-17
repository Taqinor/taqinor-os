import { useCallback, useEffect, useMemo, useState } from 'react'
import immobilierApi from '../../api/immobilierApi'

/* ============================================================================
   NTPRO1 — Arborescence du patrimoine (`/immobilier`).
   ----------------------------------------------------------------------------
   Navigation Site → Bâtiment → Niveau → Local avec fil d'Ariane cliquable :
   un local est localisable en 4 clics depuis la racine (clic 1 = site, clic 2
   = bâtiment, clic 3 = niveau, clic 4 = local). Chaque niveau de la hiérarchie
   n'appelle que l'endpoint filtré correspondant (jamais de sur-lecture).
   ========================================================================== */

function rowsFrom(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

const LEVELS = ['site', 'batiment', 'niveau', 'local']

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

      <h2>{currentLabel}</h2>
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
          </li>
        ))}
        {currentRows.length === 0 && !loading && <li>Aucun élément.</li>}
      </ul>
    </div>
  )
}

// Réexport pour les tests (LEVELS documente l'ordre de la hiérarchie).
export { LEVELS }
