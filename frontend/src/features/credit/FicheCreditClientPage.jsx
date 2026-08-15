import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import creditApi from '../../api/creditApi'
import { frenchError } from '../../lib/frenchError'
import FicheCreditClient from './FicheCreditClient'
import DefinirLimiteWizard from './DefinirLimiteWizard'

/* ============================================================================
   WIR55 — Page fiche crédit d'un client (route `/credit/clients/:id`, atteinte
   depuis l'exposition — sans URL tapée). Compose la fiche consolidée
   (`FicheCreditClient`) et l'assistant de définition de limite
   (`DefinirLimiteWizard`). L'édition reste gardée côté serveur (Directeur/Admin).

   WIR186 — la page charge désormais la limite EXISTANTE du client
   (`getLimites({client})`) : le wizard la modifie au lieu d'en créer une
   seconde (unique_together (société, client) → erreur d'intégrité), et
   l'historique NTCRD22 de cette limite — jusqu'ici servi par un endpoint sans
   aucun consommateur — est rendu sous la fiche.
   ========================================================================== */

function lignes(reponse) {
  const charge = reponse?.data
  if (Array.isArray(charge)) return charge
  if (Array.isArray(charge?.results)) return charge.results
  return []
}

export default function FicheCreditClientPage() {
  const { id } = useParams()
  const clientId = Number(id)
  const [wizardOpen, setWizardOpen] = useState(false)
  // Clé de remontage : force la fiche à se recharger après une nouvelle limite.
  const [version, setVersion] = useState(0)
  const [limite, setLimite] = useState(null)
  const [historique, setHistorique] = useState([])
  const [erreur, setErreur] = useState(null)

  const chargerLimite = useCallback(() => {
    let vivant = true
    creditApi.getLimites({ client: clientId })
      .then((res) => {
        if (!vivant) return
        const courante = lignes(res)
          .find(x => String(x.client) === String(clientId)) ?? lignes(res)[0] ?? null
        setLimite(courante)
        if (!courante?.id) { setHistorique([]); return null }
        return creditApi.getLimiteHistorique(courante.id)
          .then((h) => { if (vivant) setHistorique(h?.data?.entries ?? []) })
          // L'historique est un CONFORT : son échec (403, endpoint muet) ne
          // doit jamais masquer la fiche crédit elle-même.
          .catch(() => { if (vivant) setHistorique([]) })
      })
      .catch((err) => {
        if (vivant) setErreur(frenchError(err, 'Chargement de la limite impossible.'))
      })
    return () => { vivant = false }
  }, [clientId])

  useEffect(() => chargerLimite(), [chargerLimite, version])

  return (
    <div className="credit-fiche-page" data-testid="credit-fiche-page">
      <div className="credit-fiche-page__actions">
        <button type="button" onClick={() => setWizardOpen((o) => !o)}>
          {wizardOpen
            ? 'Fermer'
            : (limite?.id ? 'Modifier la limite' : 'Définir la limite')}
        </button>
      </div>

      {erreur && <p className="credit-fiche-page__error" role="alert">{erreur}</p>}

      {wizardOpen && (
        <DefinirLimiteWizard
          clientId={clientId}
          limite={limite}
          onDone={() => {
            setWizardOpen(false)
            setVersion((v) => v + 1)
          }}
        />
      )}

      <FicheCreditClient key={version} clientId={clientId} />

      {/* WIR186/NTCRD22 — journal des changements de la limite. */}
      {limite?.id && (
        <section className="credit-fiche-page__historique">
          <h3>Historique de la limite</h3>
          {historique.length === 0 ? (
            <p>Aucun changement enregistré sur cette limite.</p>
          ) : (
            <ul>
              {historique.map((e) => (
                <li key={e.id}>
                  <span>{e.field_label || e.field || 'Modification'}</span>
                  {(e.old_value || e.new_value) && (
                    <span> : {e.old_value || '—'} → {e.new_value || '—'}</span>
                  )}
                  {e.body && <span> — {e.body}</span>}
                  {e.acteur && <span> (par {e.acteur})</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
