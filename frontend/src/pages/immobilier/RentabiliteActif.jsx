import { useEffect, useMemo, useState } from 'react'
import immobilierApi from '../../api/immobilierApi'

/* ============================================================================
   NTPRO9 — Rentabilité par actif (`/immobilier/rentabilite`).
   ----------------------------------------------------------------------------
   Sélection d'un site OU d'un bâtiment → KPI cards (revenus, charges,
   travaux, marge nette, taux d'occupation) + tableau par local. Dégrade
   proprement quand aucun chantier n'est lié (marge = revenus - charges) et
   n'expose jamais de prix d'achat produit.
   ========================================================================== */

function rowsFrom(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

function formatMAD(value) {
  const n = Number(value)
  if (Number.isNaN(n)) return '—'
  return `${n.toFixed(2)} MAD`
}

export default function RentabiliteActif() {
  const [sites, setSites] = useState([])
  const [selection, setSelection] = useState(null) // { type: 'site'|'batiment', id }
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    immobilierApi.sites.list().then((res) => setSites(rowsFrom(res.data)))
  }, [])

  useEffect(() => {
    if (!selection) {
      setData(null)
      return undefined
    }
    let annule = false
    setLoading(true)
    setErreur(null)
    const call =
      selection.type === 'site'
        ? immobilierApi.sites.rentabilite(selection.id)
        : immobilierApi.batiments.rentabilite(selection.id)
    call
      .then((res) => {
        if (!annule) setData(res.data)
      })
      .catch(() => {
        if (!annule) setErreur('Calcul de rentabilité impossible.')
      })
      .finally(() => {
        if (!annule) setLoading(false)
      })
    return () => {
      annule = true
    }
  }, [selection])

  const kpis = useMemo(() => {
    if (!data) return []
    return [
      { label: 'Taux d\'occupation', value: `${Number(data.taux_occupation).toFixed(0)}%` },
      { label: 'Revenus', value: formatMAD(data.revenus) },
      { label: 'Charges', value: formatMAD(data.charges) },
      { label: 'Travaux', value: formatMAD(data.travaux) },
      { label: 'Marge nette', value: formatMAD(data.marge_nette) },
    ]
  }, [data])

  return (
    <div data-testid="rentabilite-actif" style={{ padding: 16 }}>
      <h1>Rentabilité par actif</h1>

      <select
        aria-label="Sélectionner un site"
        value={selection && selection.type === 'site' ? selection.id : ''}
        onChange={(e) =>
          setSelection(e.target.value ? { type: 'site', id: Number(e.target.value) } : null)
        }
      >
        <option value="">— Sélectionner un site —</option>
        {sites.map((site) => (
          <option key={site.id} value={site.id}>
            {site.nom}
          </option>
        ))}
      </select>

      {loading && <p>Calcul en cours…</p>}
      {erreur && <p role="alert">{erreur}</p>}

      {data && (
        <>
          <div data-testid="kpi-cards" style={{ display: 'flex', gap: 12, marginTop: 16 }}>
            {kpis.map((kpi) => (
              <div key={kpi.label} data-testid="kpi-card">
                <div>{kpi.label}</div>
                <strong>{kpi.value}</strong>
              </div>
            ))}
          </div>

          <table style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Local</th>
                <th>Statut</th>
                <th>Revenus</th>
              </tr>
            </thead>
            <tbody>
              {data.par_local.map((row) => (
                <tr key={row.local_id}>
                  <td>{row.reference}</td>
                  <td>{row.statut}</td>
                  <td>{formatMAD(row.revenus)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
