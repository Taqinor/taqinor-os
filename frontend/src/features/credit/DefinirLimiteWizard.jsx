import { useEffect, useState } from 'react'

import creditApi from '../../api/creditApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   NTCRD27 — Wizard « Définir une limite de crédit » (multi-étapes). Étape 1 :
   lecture seule de la position crédit existante (encours/score, réutilise
   NTCRD10). Étape 2 : limite SUGGÉRÉE (règle documentée NTCRD27, toujours
   modifiable). Étape 3 : mode de hold + confirmation.

   WIR186 — le wizard appelait TOUJOURS `createLimite`, alors que
   `LimiteCredit` est unique par (société, client) : une seconde définition sur
   le même client partait donc en erreur d'intégrité, et une limite existante
   n'était modifiable NULLE PART. Il charge désormais la limite du client et
   bascule create → `updateLimite` quand elle existe. La limite passée par le
   parent (`limite`) évite un aller-retour ; à défaut le wizard la résout
   lui-même via `getLimites({client})`.
   ========================================================================== */

export default function DefinirLimiteWizard({ clientId, limite = null, onDone }) {
  const [step, setStep] = useState(1)
  const [fiche, setFiche] = useState(null)
  const [montant, setMontant] = useState('')
  const [modeHold, setModeHold] = useState('avertissement')
  const [error, setError] = useState(null)
  const [occupe, setOccupe] = useState(false)
  // Limite EXISTANTE de ce client (null = aucune → création).
  const [existante, setExistante] = useState(limite)

  useEffect(() => {
    let vivant = true
    const limitePromise = limite
      ? Promise.resolve({ data: [limite] })
      : creditApi.getLimites({ client: clientId })
    Promise.all([
      creditApi.getFicheClient(clientId),
      creditApi.getLimiteSuggeree(clientId),
      limitePromise,
    ])
      .then(([f, s, l]) => {
        if (!vivant) return
        setFiche(f.data)
        const charge = l?.data
        const lignes = Array.isArray(charge) ? charge : (charge?.results ?? [])
        const courante = lignes.find(x => String(x.client) === String(clientId))
          ?? lignes[0] ?? null
        setExistante(courante)
        // Une limite déjà posée pré-remplit le formulaire (on la MODIFIE) ;
        // sinon on part de la suggestion NTCRD27.
        if (courante) {
          setMontant(String(courante.montant_limite ?? ''))
          setModeHold(courante.mode_hold ?? 'avertissement')
        } else {
          setMontant(String(s.data.suggestion ?? ''))
        }
      })
      .catch(() => { if (vivant) setError('Chargement impossible.') })
    return () => { vivant = false }
  }, [clientId, limite])

  async function valider() {
    if (occupe) return
    setOccupe(true)
    setError(null)
    try {
      if (existante?.id) {
        // Limite déjà posée : on la MODIFIE — jamais une seconde création
        // (unique_together (company, client) côté serveur).
        await creditApi.updateLimite(existante.id, {
          montant_limite: montant,
          mode_hold: modeHold,
        })
      } else {
        await creditApi.createLimite({
          client: clientId,
          montant_limite: montant,
          mode_hold: modeHold,
        })
      }
      if (onDone) onDone()
    } catch (err) {
      setError(frenchError(
        err,
        existante?.id
          ? 'Modification impossible.'
          : 'Création impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  if (!fiche) return <div className="credit-wizard">Chargement…</div>

  const enEdition = !!existante?.id

  return (
    <div className="credit-wizard" data-testid="credit-limite-wizard">
      {error && <p className="credit-wizard__error" role="alert">{error}</p>}

      {step === 1 && (
        <div>
          <h3>1. Position actuelle (lecture seule)</h3>
          <p>Encours : {fiche.encours} MAD</p>
          <p>Score : {fiche.lettre_score}</p>
          {enEdition && (
            <p className="credit-wizard__note">
              Ce client a déjà une limite de {existante.montant_limite} MAD :
              elle sera MODIFIÉE, pas dupliquée.
            </p>
          )}
          <button type="button" onClick={() => setStep(2)}>
            Suivant
          </button>
        </div>
      )}

      {step === 2 && (
        <div>
          <h3>{enEdition ? '2. Limite (modifiable)' : '2. Limite suggérée (modifiable)'}</h3>
          <label htmlFor="dlw-montant">Montant de la limite (MAD)</label>
          <input
            id="dlw-montant"
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
          <label htmlFor="dlw-mode">Mode de hold</label>
          <select
            id="dlw-mode"
            value={modeHold}
            onChange={(e) => setModeHold(e.target.value)}
          >
            <option value="aucun">Aucun</option>
            <option value="avertissement">Avertissement</option>
            <option value="blocage">Blocage</option>
          </select>
          <button type="button" onClick={valider} disabled={occupe}>
            {enEdition ? 'Enregistrer la limite' : 'Valider la limite'}
          </button>
        </div>
      )}
    </div>
  )
}
