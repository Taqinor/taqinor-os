import { useState } from 'react'

import { formatMAD } from '../../lib/format'
import DemandeDerogationWizard from './DemandeDerogationWizard'

/* ============================================================================
   NTCRD11 — Bannière d'alerte crédit, affichée à la confirmation d'une
   acceptation de devis. Consomme le `credit_warning` renvoyé par l'action
   `accepter` (WIR187, contrat `apps/credit/contract_samples/credit_warning.json`).
   En mode `avertissement` : orange, NON bloquant. En mode `blocage` : rouge
   franc + demande de dérogation (NTCRD9). En mode `aucun` : RIEN — pas de
   bandeau vide, pas de bruit. Aucune donnée `prix_achat`/marge n'est rendue.

   WIR188 — UN SEUL composant de demande de dérogation subsiste. Cette bannière
   embarquait sa PROPRE copie du formulaire (motif ≥ 20 caractères + appel à
   `createDerogation`), doublon exact de `DemandeDerogationWizard` (NTCRD28) :
   deux implémentations de la même écriture, deux règles de motif à garder
   synchrones, et déjà deux libellés de bouton différents. La copie inline est
   SUPPRIMÉE ; la bannière monte le wizard, qui reste le seul point d'écriture
   — c'est aussi le plus riche (il montre l'impact sur l'encours si la
   dérogation est approuvée).

   Props :
     warning   — objet `{ mode, depassement, disponible }` (WIR187) ou null.
     clientId  — client concerné (pour la demande de dérogation).
     montant   — montant TTC de la transaction proposée.
     devisId   — devis concerné (optionnel, contexte de la dérogation).
     onDerogationDemandee — callback après soumission réussie.
   ========================================================================== */

// Le serveur sérialise les montants en TEXTE décimal (jamais un flottant) :
// une comparaison directe `warning.depassement > 0` sur « "0.00" » serait
// FAUSSE en JS (comparaison de chaîne). On convertit explicitement.
const nombre = (v) => {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

export default function CreditWarningBanner({
  warning,
  clientId,
  montant,
  devisId = null,
  onDerogationDemandee,
}) {
  const [done, setDone] = useState(false)

  if (!warning || !warning.mode || warning.mode === 'aucun') return null

  const bloquant = warning.mode === 'blocage'
  const depassement = nombre(warning.depassement)
  const disponible = warning.disponible == null ? null : nombre(warning.disponible)

  return (
    <div
      className={`credit-banner credit-banner--${bloquant ? 'block' : 'warn'}`}
      role={bloquant ? 'alert' : 'status'}
      data-testid="credit-warning-banner"
      data-mode={warning.mode}
    >
      <p className="credit-banner__message">
        {bloquant
          ? 'Client en blocage crédit : dépassement de sa limite. '
          : 'Attention : ce client approche/dépasse sa limite de crédit. '}
        {depassement > 0 && `Dépassement estimé : ${formatMAD(depassement)}. `}
        {depassement <= 0 && disponible !== null
          && `Disponible : ${formatMAD(disponible)}.`}
      </p>

      {bloquant && !done && (
        <DemandeDerogationWizard
          clientId={clientId}
          montant={montant}
          devisId={devisId}
          onSubmitted={() => {
            setDone(true)
            if (onDerogationDemandee) onDerogationDemandee()
          }}
        />
      )}

      {done && (
        <p className="credit-banner__ok">
          Demande de dérogation soumise — en attente de décision.
        </p>
      )}
    </div>
  )
}
