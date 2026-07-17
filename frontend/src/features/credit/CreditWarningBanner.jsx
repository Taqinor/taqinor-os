import { useState } from 'react'

import creditApi from '../../api/creditApi'

/* ============================================================================
   NTCRD11 — Bannière d'alerte crédit affichée AVANT confirmation d'une
   acceptation de devis / création de BC. Consomme le `credit_warning` renvoyé
   par les hooks NTCRD7/8 (côté ventes). En mode `avertissement` : badge orange
   NON bloquant. En mode `blocage` : rouge franc + bouton « Demander une
   dérogation » (obligatoire) qui pré-remplit et soumet une DerogationCredit
   (NTCRD9) via l'API crédit. Aucune donnée `prix_achat`/marge n'est rendue.

   Props :
     warning   — objet `{ mode, depassement, disponible }` (NTCRD7/8) ou null.
     clientId  — client concerné (pour la demande de dérogation).
     montant   — montant TTC de la transaction proposée.
     devisId   — devis concerné (optionnel, contexte de la dérogation).
     onDerogationDemandee — callback après soumission réussie.
   ========================================================================== */

export default function CreditWarningBanner({
  warning,
  clientId,
  montant,
  devisId = null,
  onDerogationDemandee,
}) {
  const [motif, setMotif] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)

  if (!warning || warning.mode === 'aucun') return null

  const bloquant = warning.mode === 'blocage'

  async function demanderDerogation() {
    setSubmitting(true)
    setError(null)
    try {
      await creditApi.createDerogation({
        client: clientId,
        montant_demande: montant,
        devis: devisId,
        motif,
      })
      setDone(true)
      if (onDerogationDemandee) onDerogationDemandee()
    } catch {
      setError('Échec de la demande de dérogation.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className={`credit-banner credit-banner--${bloquant ? 'block' : 'warn'}`}
      role={bloquant ? 'alert' : 'status'}
      data-testid="credit-warning-banner"
    >
      <p className="credit-banner__message">
        {bloquant
          ? 'Client en blocage crédit : dépassement de sa limite. '
          : 'Attention : ce client approche/dépasse sa limite de crédit. '}
        {warning.depassement > 0 &&
          `Dépassement estimé : ${Number(warning.depassement).toLocaleString('fr-FR')} MAD.`}
      </p>

      {bloquant && !done && (
        <div className="credit-banner__derogation">
          <label>
            Motif de la dérogation
            <textarea
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              minLength={20}
              placeholder="Justification (≥ 20 caractères)"
            />
          </label>
          <button
            type="button"
            disabled={submitting || motif.trim().length < 20}
            onClick={demanderDerogation}
          >
            Demander une dérogation
          </button>
          {error && <span className="credit-banner__error">{error}</span>}
        </div>
      )}

      {done && (
        <p className="credit-banner__ok">
          Demande de dérogation soumise — en attente de décision.
        </p>
      )}
    </div>
  )
}
