import { useEffect, useState } from 'react'
import fpaApi from '../../api/fpaApi'
import { Button, Card } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTFPA22 — Écran Variance Analysis.
   ----------------------------------------------------------------------------
   Tableau croisé département × catégorie avec 3 colonnes (prévu/réel/forecast)
   + écarts colorés, drill-down clic → détail mensuel + fil de commentaires
   (NTFPA20). Un directeur financier voit en un écran quels départements
   dépassent leur budget de plus de 10 % ce mois-ci, avec justification si
   commentée.
   ========================================================================== */

const MOIS_LABELS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

export default function VariancePage() {
  const [cycles, setCycles] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [mois, setMois] = useState(1)
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [detail, setDetail] = useState(null)
  const [commentaires, setCommentaires] = useState([])
  const [nouveauTexte, setNouveauTexte] = useState('')

  useEffect(() => {
    fpaApi.getCycles()
      .then((res) => setCycles(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les cycles.'))
  }, [])

  const charger = async () => {
    if (!cycleId) return
    setError(null)
    try {
      const res = await fpaApi.variance({ cycle: cycleId, mois })
      setRows(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
    } catch {
      setError('Impossible de charger la variance.')
    }
  }

  const ouvrirDetail = async (row) => {
    setDetail(row)
    try {
      const res = await fpaApi.getCommentairesVariance({
        cycle: cycleId, departement: row.departement_id,
        categorie: row.categorie, mois,
      })
      setCommentaires(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
    } catch {
      setCommentaires([])
    }
  }

  const ajouterCommentaire = async () => {
    if (!detail || !nouveauTexte.trim()) return
    try {
      await fpaApi.createCommentaireVariance({
        cycle: cycleId, departement: detail.departement_id,
        categorie: detail.categorie, mois, texte: nouveauTexte,
      })
      setNouveauTexte('')
      ouvrirDetail(detail)
    } catch {
      setError('Le commentaire n’a pas pu être enregistré.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Analyse des écarts (variance)"
        subtitle="Prévu / Réel / Forecast par département × catégorie"
        actions={<Button onClick={charger} disabled={!cycleId}>Actualiser</Button>}
      />
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <select
          aria-label="Cycle budgétaire"
          value={cycleId}
          onChange={(e) => setCycleId(e.target.value)}
        >
          <option value="">— Cycle budgétaire —</option>
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
        <select aria-label="Mois" value={mois} onChange={(e) => setMois(Number(e.target.value))}>
          {MOIS_LABELS.map((label, i) => (
            <option key={label} value={i + 1}>{label}</option>
          ))}
        </select>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger, #c00)' }}>{error}</p>}
      <Card>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 8 }}>Département</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Catégorie</th>
                <th style={{ padding: 8 }}>Prévu</th>
                <th style={{ padding: 8 }}>Réel</th>
                <th style={{ padding: 8 }}>Forecast</th>
                <th style={{ padding: 8 }}>Écart P/R</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={`${r.departement_id}-${r.categorie}-${i}`}
                  onClick={() => ouvrirDetail(r)}
                  style={{ cursor: 'pointer', background: r.depassement ? 'var(--danger-bg, #fee2e2)' : undefined }}
                >
                  <td style={{ padding: 8 }}>{r.departement}</td>
                  <td style={{ padding: 8 }}>{r.categorie}</td>
                  <td style={{ padding: 8 }}>{formatMAD(Number(r.prevu || 0))}</td>
                  <td style={{ padding: 8 }}>{formatMAD(Number(r.reel || 0))}</td>
                  <td style={{ padding: 8 }}>{formatMAD(Number(r.forecast || 0))}</td>
                  <td style={{ padding: 8, fontWeight: r.depassement ? 700 : 400 }}>
                    {formatMAD(Number(r.ecart_prevu_reel_eur || 0))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {detail && (
        <Card>
          <h3>Commentaires — {detail.departement} / {detail.categorie}</h3>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {commentaires.map((c) => (
              <li key={c.id} style={{ padding: 6, borderBottom: '1px solid var(--border, #eee)' }}>
                <strong>{c.auteur_nom || '—'}</strong> : {c.texte}
              </li>
            ))}
          </ul>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              aria-label="Nouveau commentaire"
              value={nouveauTexte}
              onChange={(e) => setNouveauTexte(e.target.value)}
              placeholder="Expliquer cet écart…"
              style={{ flex: 1 }}
            />
            <Button onClick={ajouterCommentaire}>Commenter</Button>
          </div>
        </Card>
      )}
    </div>
  )
}
