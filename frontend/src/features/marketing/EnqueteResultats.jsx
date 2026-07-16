import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import { lienPublic } from './EnqueteBuilder'

/* ============================================================================
   NTMKT8 — Page résultats d'une enquête : graphiques par question, taux de
   complétion/abandon, export XLSX.
   ----------------------------------------------------------------------------
   `marketing/enquetes/<id>/resultats/` (`apps.compta.services.
   analytics_enquete` — répartition des choix, moyenne/NPS des échelles,
   nuage texte, `_completion`), `resultats/export/` (XLSX déjà côté serveur).
   Graphiques en barres HTML pures (pas de nouvelle dépendance de charting).
   ========================================================================== */

function BarreRepartition({ repartition }) {
  const entries = Object.entries(repartition || {})
  const max = Math.max(1, ...entries.map(([, n]) => n))
  return (
    <div data-testid="enquete-resultat-repartition">
      {entries.map(([valeur, n]) => (
        <div key={valeur} style={{ display: 'flex', alignItems: 'center', gap: 6,
          marginBottom: 3 }}>
          <span style={{ fontSize: '0.78rem', minWidth: 100 }}>{valeur}</span>
          <div style={{ background: '#0d9488', height: 10,
            width: `${(n / max) * 100}%`, borderRadius: 3, minWidth: 4 }} />
          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{n}</span>
        </div>
      ))}
      {entries.length === 0 && <p style={{ color: '#94a3b8', margin: 0 }}>Aucune réponse.</p>}
    </div>
  )
}

export default function EnqueteResultats() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [enquete, setEnquete] = useState(null)
  const [resultats, setResultats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([marketingApi.enquetes.get(id), marketingApi.enquetes.resultats(id)])
      .then(([eRes, rRes]) => { setEnquete(eRes.data); setResultats(rRes.data) })
      .catch(() => setErr('Enquête introuvable.'))
      .finally(() => setLoading(false))
  }, [id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const exporter = async () => {
    setErr('')
    try {
      const r = await marketingApi.enquetes.resultatsExport(id)
      marketingApi.downloadBlob(r.data, `participations-${id}.xlsx`)
    } catch {
      setErr('Export impossible.')
    }
  }

  if (loading) return <div className="page"><p className="page-loading">Chargement…</p></div>
  if (!enquete) return <div className="page"><p style={{ color: '#dc2626' }}>{err || 'Introuvable.'}</p></div>

  const completion = resultats?._completion || { total: 0, completes: 0, taux_completion_pct: 0 }

  return (
    <div className="page">
      <div className="page-header">
        <button className="btn btn-light" onClick={() => navigate('/marketing/enquetes')}>
          ← Enquêtes
        </button>
        <h2>{enquete.titre} — résultats</h2>
        <button className="btn btn-light" data-testid="enquete-exporter" onClick={exporter}>
          Exporter XLSX
        </button>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      <div data-testid="enquete-completion" style={{ marginBottom: '1rem' }}>
        {completion.total} réponse(s), {completion.completes} complète(s)
        {' '}({completion.taux_completion_pct}% de complétion)
      </div>

      {enquete.token && (
        <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
          Lien public : <code>{lienPublic(enquete.token)}</code>
        </p>
      )}

      {(enquete.questions || []).map(q => {
        const r = resultats?.[q.id]
        return (
          <section key={q.id} data-testid="enquete-resultat-question"
            style={{ marginBottom: '1rem', border: '1px solid #e2e8f0', borderRadius: 8,
              padding: '0.6rem 0.8rem' }}>
            <h4 style={{ margin: '0 0 6px' }}>{q.libelle}</h4>
            {r?.type === 'choix' && <BarreRepartition repartition={r.repartition} />}
            {(r?.type === 'echelle' || r?.type === 'nps') && (
              <p style={{ margin: 0 }}>
                Moyenne : {r.moyenne} ({r.n} réponse(s))
                {r.type === 'nps' && r.nps !== undefined && ` — NPS : ${r.nps}`}
              </p>
            )}
            {r?.type === 'texte' && (
              <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
                {(r.reponses || []).slice(0, 10).map((t, i) => <li key={i}>{t}</li>)}
                {(r.reponses || []).length === 0 && <li style={{ color: '#94a3b8' }}>Aucune réponse</li>}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}
