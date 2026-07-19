import { useState } from 'react'
import { useParams } from 'react-router-dom'

import FicheCreditClient from './FicheCreditClient'
import DefinirLimiteWizard from './DefinirLimiteWizard'

/* ============================================================================
   WIR55 — Page fiche crédit d'un client (route `/credit/clients/:id`, atteinte
   depuis l'exposition — sans URL tapée). Compose la fiche consolidée
   (`FicheCreditClient`) et l'assistant de définition de limite
   (`DefinirLimiteWizard`) pour que le Directeur consulte ET pose une limite
   depuis le même écran. L'édition reste gardée côté serveur (Directeur/Admin).
   ========================================================================== */

export default function FicheCreditClientPage() {
  const { id } = useParams()
  const clientId = Number(id)
  const [wizardOpen, setWizardOpen] = useState(false)
  // Clé de remontage : force la fiche à se recharger après une nouvelle limite.
  const [version, setVersion] = useState(0)

  return (
    <div className="credit-fiche-page" data-testid="credit-fiche-page">
      <div className="credit-fiche-page__actions">
        <button type="button" onClick={() => setWizardOpen((o) => !o)}>
          {wizardOpen ? 'Fermer' : 'Définir la limite'}
        </button>
      </div>

      {wizardOpen && (
        <DefinirLimiteWizard
          clientId={clientId}
          onDone={() => {
            setWizardOpen(false)
            setVersion((v) => v + 1)
          }}
        />
      )}

      <FicheCreditClient key={version} clientId={clientId} />
    </div>
  )
}
