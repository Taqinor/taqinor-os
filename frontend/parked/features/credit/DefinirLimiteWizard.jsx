import { useEffect, useState } from 'react'

import creditApi from '../../api/creditApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   NTCRD27 — Wizard « Définir une limite de crédit » (multi-étapes). Réservé
   Directeur/Administrateur (le backend re-vérifie sur l'écriture). Étape 1 :
   lecture seule de la position crédit existante (encours/score, réutilise
   NTCRD10). Étape 2 : limite SUGGÉRÉE (règle documentée NTCRD27, toujours
   modifiable). Étape 3 : mode de hold + confirmation. ≤ 4 clics jusqu'à une
   LimiteCredit cohérente.

   WIR186 — l'assistant appelait TOUJOURS `createLimite`, y compris sur un
   client qui avait déjà une limite : le second POST se heurtait à l'unicité
   `(company, client)` — une erreur d'INTÉGRITÉ, pas un message métier, et la
   limite restait donc immodifiable. La page parente charge la limite existante
   et la passe en prop : elle pré-remplit les champs et fait basculer la
   validation sur `updateLimite`. JAMAIS de seconde création. Un refus serveur
   (403 de rôle, doublon, montant invalide) est affiché TEL QUEL.
   ========================================================================== */

export default function DefinirLimiteWizard({ clientId, limite = null, onDone }) {
  const [step, setStep] = useState(1)
  const edition = !!limite?.id
  const [fiche, setFiche] = useState(null)
  // En ÉDITION, les champs partent de la valeur RÉELLEMENT enregistrée — via
  // un initialiseur paresseux, jamais un `setState` dans un effet (qui
  // déclencherait un rendu en cascade, react-hooks/set-state-in-effect). Le
  // point de montage passe `key={limite?.id}` : changer de limite remonte le
  // composant, donc l'initialiseur rejoue.
  const [montant, setMontant] = useState(
    () => (edition ? String(limite.montant_limite ?? '') : ''))
  const [modeHold, setModeHold] = useState(
    () => (edition ? (limite.mode_hold || 'avertissement') : 'avertissement'))
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // En ÉDITION, la limite SUGGÉRÉE n'a pas lieu d'être demandée : elle
    // écraserait la décision déjà prise par le Directeur.
    if (edition) {
      creditApi.getFicheClient(clientId)
        .then((f) => setFiche(f.data))
        .catch(() => setError('Chargement impossible.'))
      return
    }
    Promise.all([
      creditApi.getFicheClient(clientId),
      creditApi.getLimiteSuggeree(clientId),
    ])
      .then(([f, s]) => {
        setFiche(f.data)
        setMontant(String(s.data.suggestion ?? ''))
      })
      .catch(() => setError('Chargement impossible.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, limite?.id])

  async function valider() {
    setError(null)
    setBusy(true)
    try {
      if (edition) {
        await creditApi.updateLimite(limite.id, {
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
        err, edition ? 'Modification impossible.' : 'Création impossible.'))
    } finally {
      setBusy(false)
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
          <h3>{edition ? '2. Limite actuelle (modifiable)' : '2. Limite suggérée (modifiable)'}</h3>
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
          <button type="button" onClick={valider} disabled={busy}>
            {edition ? 'Enregistrer la limite' : 'Valider la limite'}
          </button>
        </div>
      )}
    </div>
  )
}
