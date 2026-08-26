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
   (`DefinirLimiteWizard`) pour que le Directeur consulte ET pose une limite
   depuis le même écran. L'édition reste gardée côté serveur (Directeur/Admin).

   WIR186 — DEUX défauts corrigés ici :

   1. La limite n'était JAMAIS modifiable. L'assistant appelait toujours
      `createLimite` : sur un client qui en avait déjà une, le second POST se
      heurtait à l'unicité `(company, client)` — une erreur d'intégrité, pas un
      message métier. On charge donc la limite EXISTANTE et on la passe à
      l'assistant, qui bascule alors sur `updateLimite` : jamais de seconde
      création.
   2. `GET /credit/limites/<id>/historique/` (NTCRD22 — qui a changé le montant
      ou le mode de hold, et quand) n'avait AUCUN appelant : la traçabilité
      était écrite côté serveur et invisible. Elle est rendue ci-dessous.
   ========================================================================== */

function HistoriqueLimite({ limiteId }) {
  const [entries, setEntries] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    // Pas de limite = pas d'historique : on ne pose AUCUN state ici (un
    // `setState` synchrone dans un effet déclenche des rendus en cascade,
    // react-hooks/set-state-in-effect). Le composant rend `null` de toute
    // façon quand `limiteId` est absent.
    if (!limiteId) return undefined
    let vivant = true
    creditApi.getLimiteHistorique(limiteId)
      .then((r) => { if (vivant) setEntries(r?.data?.entries ?? []) })
      .catch((err) => {
        if (vivant) setErreur(frenchError(err, 'Historique illisible.'))
      })
    return () => { vivant = false }
  }, [limiteId])

  if (!limiteId) return null
  return (
    <section className="credit-limite-historique" data-testid="credit-limite-historique">
      <h4>Historique de la limite</h4>
      {erreur && <p role="alert">{erreur}</p>}
      {!erreur && entries === null && <p>Chargement…</p>}
      {!erreur && entries !== null && entries.length === 0 && (
        <p>Aucun changement consigné.</p>
      )}
      {!erreur && entries !== null && entries.length > 0 && (
        <ul>
          {entries.map((e) => (
            <li key={e.id}>
              <span>{e.created_at}</span>
              {e.acteur ? <span> · {e.acteur}</span> : null}
              <span>
                {' — '}
                {e.body
                  ? e.body
                  : `${e.field_label || e.field} : ${e.old_value || '—'} → ${e.new_value || '—'}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function FicheCreditClientPage() {
  const { id } = useParams()
  const clientId = Number(id)
  const [wizardOpen, setWizardOpen] = useState(false)
  // Clé de remontage : force la fiche à se recharger après une nouvelle limite.
  const [version, setVersion] = useState(0)
  // WIR186 — la limite EXISTANTE du client (null = aucune → création).
  const [limite, setLimite] = useState(null)
  const [limiteChargee, setLimiteChargee] = useState(false)

  // Aucun `setState` SYNCHRONE ici : tout passe par un callback de promesse
  // (react-hooks/set-state-in-effect). `limiteChargee` ne sert que de porte
  // d'OUVERTURE de l'assistant — il n'a jamais à repasser à `false` : un
  // rechargement suit toujours la fermeture de l'assistant (`onDone`).
  const chargerLimite = useCallback(
    () => creditApi.getLimites({ client: clientId })
      .then((r) => {
        const lignes = r?.data?.results ?? r?.data ?? []
        setLimite(Array.isArray(lignes) && lignes.length > 0 ? lignes[0] : null)
      })
      .catch(() => setLimite(null))
      .finally(() => setLimiteChargee(true)),
    [clientId],
  )

  useEffect(() => { chargerLimite() }, [chargerLimite])

  return (
    <div className="credit-fiche-page" data-testid="credit-fiche-page">
      <div className="credit-fiche-page__actions">
        <button type="button" onClick={() => setWizardOpen((o) => !o)}>
          {wizardOpen ? 'Fermer' : (limite ? 'Modifier la limite' : 'Définir la limite')}
        </button>
      </div>

      {wizardOpen && limiteChargee && (
        <DefinirLimiteWizard
          // WIR186 — l'assistant initialise ses champs depuis la limite : sans
          // cette clé, passer d'une limite à l'autre garderait les valeurs de
          // la précédente (l'initialiseur paresseux ne rejoue qu'au montage).
          key={limite?.id ?? 'nouvelle'}
          clientId={clientId}
          limite={limite}
          onDone={() => {
            setWizardOpen(false)
            setVersion((v) => v + 1)
            chargerLimite()
          }}
        />
      )}

      <FicheCreditClient key={version} clientId={clientId} />

      <HistoriqueLimite key={`h${version}`} limiteId={limite?.id} />
    </div>
  )
}
