import { useEffect, useState } from 'react'

import creditApi from '../../api/creditApi'

/* ============================================================================
   NTCRD27 — Wizard « Définir une limite de crédit » (multi-étapes), pour un
   client SANS LimiteCredit. Réservé Directeur/Administrateur (le backend
   re-vérifie sur la création). Étape 1 : lecture seule de la position crédit
   existante (encours/score, réutilise NTCRD10). Étape 2 : limite SUGGÉRÉE
   (règle documentée NTCRD27, toujours modifiable). Étape 3 : mode de hold +
   confirmation. ≤ 4 clics jusqu'à une LimiteCredit cohérente.
   ========================================================================== */

export default function DefinirLimiteWizard({ clientId, onDone }) {
  const [step, setStep] = useState(1)
  const [fiche, setFiche] = useState(null)
  const [montant, setMontant] = useState('')
  const [modeHold, setModeHold] = useState('avertissement')
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      creditApi.getFicheClient(clientId),
      creditApi.getLimiteSuggeree(clientId),
    ])
      .then(([f, s]) => {
        setFiche(f.data)
        setMontant(String(s.data.suggestion ?? ''))
      })
      .catch(() => setError('Chargement impossible.'))
  }, [clientId])

  async function valider() {
    setError(null)
    try {
      await creditApi.createLimite({
        client: clientId,
        montant_limite: montant,
        mode_hold: modeHold,
      })
      if (onDone) onDone()
    } catch {
      setError('Création impossible.')
    }
  }

  if (!fiche) return <div className="credit-wizard">Chargement…</div>

  return (
    <div className="credit-wizard" data-testid="credit-limite-wizard">
      {error && <p className="credit-wizard__error">{error}</p>}

      {step === 1 && (
        <div>
          <h3>1. Position actuelle (lecture seule)</h3>
          <p>Encours : {fiche.encours} MAD</p>
          <p>Score : {fiche.lettre_score}</p>
          <button type="button" onClick={() => setStep(2)}>
            Suivant
          </button>
        </div>
      )}

      {step === 2 && (
        <div>
          <h3>2. Limite suggérée (modifiable)</h3>
          <input
            type="number"
            step="any"
            value={montant}
            onChange={(e) => setMontant(e.target.value)}
          />
          <button type="button" onClick={() => setStep(3)}>
            Suivant
          </button>
        </div>
      )}

      {step === 3 && (
        <div>
          <h3>3. Mode de hold + confirmation</h3>
          <select
            value={modeHold}
            onChange={(e) => setModeHold(e.target.value)}
          >
            <option value="aucun">Aucun</option>
            <option value="avertissement">Avertissement</option>
            <option value="blocage">Blocage</option>
          </select>
          <button type="button" onClick={valider}>
            Valider la limite
          </button>
        </div>
      )}
    </div>
  )
}
