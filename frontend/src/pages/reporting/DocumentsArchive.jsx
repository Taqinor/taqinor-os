import { useEffect, useState } from 'react'
import api from '../../api/axios'
import reportingApi from '../../api/reportingApi'
import { typeLabel, sortDocsDesc } from './archiveDocs'

// N32 — Archive documentaire (par client ou par chantier). Composant
// réutilisable : agrège tous les documents générés (devis, factures, avoirs,
// bons de commande + documents post-vente) et pointe vers les endpoints de
// téléchargement EXISTANTS, qui régénèrent le PDF à la demande. Lecture seule.
//
// Props :
//   - kind : 'client' | 'chantier'
//   - id   : identifiant du client ou du chantier
//
// Utilisable comme page (via les wrappers ArchiveClientPage / ArchiveChantierPage)
// ou intégrable en panneau dans la fiche client / chantier.
export default function DocumentsArchive({ kind, id }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    const run = async () => {
      await Promise.resolve()
      if (!alive) return
      setLoading(true)
      setError(null)
      try {
        const r = kind === 'chantier'
          ? await reportingApi.getArchiveChantier(id)
          : await reportingApi.getArchiveClient(id)
        if (alive) setData(r.data)
      } catch {
        if (alive) setError('Archive indisponible.')
      }
      if (alive) setLoading(false)
    }
    if (id != null) run()
    return () => { alive = false }
  }, [kind, id])

  const openDoc = async (doc) => {
    if (!doc.download_url) {
      alert('Ce document n’a pas de PDF téléchargeable.')
      return
    }
    try {
      // download_url est un chemin /api/django/... ; l'intercepteur axios ne le
      // préfixe pas (il commence déjà par /api/). Cookies httpOnly envoyés.
      const r = await api.get(doc.download_url, { responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch {
      alert('Document indisponible.')
    }
  }

  if (loading) return <p className="page-loading">Chargement…</p>
  if (error) return <p style={empty}>{error}</p>
  if (!data) return null

  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: '1.1rem 1.3rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)' }}>
      <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#1e293b', margin: '0 0 0.75rem' }}>
        Documents ({data.count})
      </h3>
      {data.documents.length === 0 ? (
        <p style={empty}>Aucun document.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Type</th><th>Référence</th><th>Date</th><th /></tr>
          </thead>
          <tbody>
            {sortDocsDesc(data.documents).map((d, i) => (
              <tr key={i}>
                <td>{typeLabel(d)}</td>
                <td>{d.reference || '—'}</td>
                <td>{d.date || '—'}</td>
                <td className="ta-right">
                  {d.download_url ? (
                    <button className="btn btn-sm btn-outline" onClick={() => openDoc(d)}>
                      Ouvrir le PDF
                    </button>
                  ) : (
                    <span style={{ color: '#94a3b8', fontSize: 12 }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

const empty = { textAlign: 'center', color: '#94a3b8', padding: '1.5rem' }
