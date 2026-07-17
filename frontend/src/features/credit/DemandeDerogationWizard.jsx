import { useEffect, useState } from 'react'

import creditApi from '../../api/creditApi'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTCRD28 — Wizard « Demande de dérogation » (côté commercial), déclenché
   depuis la bannière NTCRD11. Pré-remplit client/montant/devis|BC, exige un
   motif ≥ 20 caractères, affiche en aperçu l'impact sur l'encours si approuvée,
   puis soumet à DerogationCredit (NTCRD9). Le backend notifie automatiquement
   le(s) Directeur(s) à la création (NTCRD28).
   ========================================================================== */

export default function DemandeDerogationWizard({
  clientId,
  montant,
  devisId = null,
  onSubmitted,
}) {
  const [motif, setMotif] = useState('')
  const [fiche, setFiche] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    creditApi
      .getFicheClient(clientId)
      .then((res) => setFiche(res.data))
      .catch(() => {})
  }, [clientId])

  const motifValide = motif.trim().length >= 20
  const encoursApres =
    fiche && fiche.encours !== null
      ? Number(fiche.encours) + Number(montant || 0)
      : null

  async function soumettre() {
    setSubmitting(true)
    setError(null)
    try {
      await creditApi.createDerogation({
        client: clientId,
        montant_demande: montant,
        devis: devisId,
        motif,
      })
      if (onSubmitted) onSubmitted()
    } catch {
      setError('Soumission impossible.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="credit-derog-wizard" data-testid="credit-derogation-wizard">
      <h3>Demande de dérogation crédit</h3>
      <p>Montant concerné : {formatMAD(montant || 0)}</p>
      {encoursApres !== null && (
        <p>
          Encours si approuvée : {formatMAD(encoursApres)}
        </p>
      )}
      <label>
        Motif (obligatoire, ≥ 20 caractères)
        <textarea
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          minLength={20}
        />
      </label>
      {error && <p className="credit-derog-wizard__error">{error}</p>}
      <button type="button" disabled={!motifValide || submitting} onClick={soumettre}>
        Soumettre la demande
      </button>
    </div>
  )
}
