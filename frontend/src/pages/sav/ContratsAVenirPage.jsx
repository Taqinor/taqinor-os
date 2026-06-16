import { useEffect, useState } from 'react'
import savApi from '../../api/savApi'

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

function EcheanceBadge({ contrat }) {
  const color = contrat.est_due ? '#dc2626' : '#d97706'
  const n = contrat.jours_avant_visite
  let label
  if (contrat.est_due) {
    label = n != null && n < 0 ? `Due (en retard de ${-n} j)` : 'Due aujourd’hui'
  } else {
    label = `Dans ${n} j`
  }
  return (
    <span className="badge" style={{
      background: `${color}22`, color, padding: '2px 8px',
      borderRadius: 6, fontSize: 12, whiteSpace: 'nowrap',
    }}>{label}</span>
  )
}

export default function ContratsAVenirPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [message, setMessage] = useState(null)

  // Échéances calculées à la lecture côté serveur — aucune génération ici.
  const reload = () =>
    savApi.getContratsAVenir(false)
      .then((r) => setItems(r.data ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  useEffect(() => { reload() }, [])

  // Génère TOUS les tickets dus en une fois (idempotent côté serveur).
  const genererTous = async () => {
    setGenerating(true)
    setMessage(null)
    try {
      const r = await savApi.getContratsAVenir(true)
      setItems(r.data ?? [])
      setMessage('Tickets dus générés (les visites non dues sont ignorées).')
    } catch {
      setMessage('Échec de la génération des tickets dus.')
    } finally {
      setGenerating(false)
    }
  }

  // Génère le ticket dû d'un seul contrat.
  const genererUn = async (id) => {
    try {
      await savApi.genererTicketsDus(id)
      reload()
    } catch { /* silencieux */ }
  }

  const dus = items.filter((c) => c.est_due)

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Maintenance — visites à venir</h1>
        <div className="page-subtitle">
          {items.length} contrat(s) ({dus.length} due(s))
        </div>
        <button type="button" className="btn btn-primary"
                disabled={generating || dus.length === 0} onClick={genererTous}>
          {generating ? 'Génération…' : 'Générer les tickets dus'}
        </button>
      </div>

      {message && <div className="form-info-box" role="status">{message}</div>}

      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="gen-hint">Aucune visite due ou à venir prochainement.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Libellé</th>
                <th>Client</th>
                <th className="m-hide">Chantier</th>
                <th>Prochaine visite</th>
                <th>Échéance</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td>{c.libelle ?? '—'}</td>
                  <td>{c.client_nom ?? '—'}</td>
                  <td className="m-hide">{c.installation_reference ?? '—'}</td>
                  <td>{formatDateFR(c.prochaine_visite)}</td>
                  <td><EcheanceBadge contrat={c} /></td>
                  <td>
                    {c.est_due ? (
                      <button type="button" className="btn btn-sm btn-outline"
                              onClick={() => genererUn(c.id)}>
                        Générer le ticket
                      </button>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
