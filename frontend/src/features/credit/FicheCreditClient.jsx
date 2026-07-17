import { useEffect, useState } from 'react'

import creditApi from '../../api/creditApi'

/* ============================================================================
   NTCRD10 — Fiche crédit client (composant autonome, réutilisable comme onglet
   sur la fiche client CRM). Affiche limite, encours, disponible, % utilisé
   (barre de progression), lettre de score, mode de hold actif et l'historique
   des dérogations. Aucune donnée `prix_achat`/marge n'est jamais demandée ni
   rendue. L'édition de la limite est gardée côté serveur (Directeur/Admin).
   ========================================================================== */

function formatMAD(value) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toLocaleString('fr-FR')} MAD`
}

export default function FicheCreditClient({ clientId }) {
  const [fiche, setFiche] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    creditApi
      .getFicheClient(clientId)
      .then((res) => {
        if (alive) {
          setFiche(res.data)
          setError(null)
        }
      })
      .catch(() => {
        if (alive) setError('Impossible de charger la fiche crédit.')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [clientId])

  if (loading) return <div className="credit-fiche">Chargement…</div>
  if (error) return <div className="credit-fiche credit-fiche--error">{error}</div>
  if (!fiche) return null

  const pct =
    fiche.pct_utilise === null || fiche.pct_utilise === undefined
      ? null
      : Math.min(100, Math.round(fiche.pct_utilise * 100))

  return (
    <div className="credit-fiche" data-testid="credit-fiche">
      <div className="credit-fiche__grid">
        <div>
          <span className="credit-fiche__label">Limite</span>
          <span className="credit-fiche__value">{formatMAD(fiche.limite)}</span>
        </div>
        <div>
          <span className="credit-fiche__label">Encours</span>
          <span className="credit-fiche__value">{formatMAD(fiche.encours)}</span>
        </div>
        <div>
          <span className="credit-fiche__label">Disponible</span>
          <span className="credit-fiche__value">
            {formatMAD(fiche.disponible)}
          </span>
        </div>
        <div>
          <span className="credit-fiche__label">Score</span>
          <span className="credit-fiche__value">{fiche.lettre_score}</span>
        </div>
        <div>
          <span className="credit-fiche__label">Mode de hold</span>
          <span className="credit-fiche__value">{fiche.mode_hold || 'aucun'}</span>
        </div>
      </div>

      {pct !== null && (
        <div className="credit-fiche__progress" aria-label="Taux d'utilisation">
          <div
            className={`credit-fiche__bar${fiche.depasse ? ' credit-fiche__bar--over' : ''}`}
            style={{ width: `${pct}%` }}
          />
          <span className="credit-fiche__pct">{pct}%</span>
        </div>
      )}

      <h4>Historique des dérogations</h4>
      {fiche.derogations.length === 0 ? (
        <p>Aucune dérogation.</p>
      ) : (
        <ul className="credit-fiche__derogations">
          {fiche.derogations.map((d) => (
            <li key={d.id}>
              {formatMAD(d.montant_demande)} — {d.statut}
              {d.est_valide ? ' (valide)' : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
