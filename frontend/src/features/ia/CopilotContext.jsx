// NTAI10 — Copilote CONTEXTUEL : ce que dit la fiche ouverte, et quoi faire.
//
// Le tiroir Copilote (FG350) répond à des questions sur TOUTE la base ; ce
// panneau-ci répond sur LA FICHE qu'on a sous les yeux : un résumé de la
// situation (NTAI8), 1 à 3 actions priorisées (NTAI9) et un brouillon de
// réponse (NTAI11).
//
// TROIS RÈGLES DE LA MAISON, visibles ici :
//   * l'IA PROPOSE, l'humain confirme — cliquer une action ne l'exécute pas :
//     elle passe par le flux propose → confirme EXISTANT de l'agent (AG3),
//     qui affiche sa carte de confirmation ;
//   * le brouillon n'est JAMAIS envoyé (le serveur renvoie `envoye: false`) ;
//   * sans clé LLM, le serveur répond 503 et on affiche « Assistant
//     indisponible » — jamais un écran cassé, jamais un chiffre inventé.
//
// Utilisable de deux façons : avec des props explicites
// (`<CopilotContext contentType="crm.lead" objectId={12} />`) depuis n'importe
// quelle fiche, ou sans props — la fiche est alors déduite de l'URL courante
// (`ficheDepuisChemin`, pure et testée).
import { useCallback, useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useLocation } from 'react-router-dom'
import { Sparkles, ListChecks, PenLine } from 'lucide-react'
import aiGovernanceApi from '../../api/aiGovernanceApi'
import { Button, Spinner, Textarea } from '../../ui'
import { queryAgent } from './store/iaSlice'

/** Correspondance URL → fiche. Étendre ici quand un écran détail apparaît. */
const ROUTES_FICHE = [
  { motif: /^\/crm\/leads\/(\d+)/, contentType: 'crm.lead' },
  { motif: /^\/contrats\/(\d+)/, contentType: 'contrats.contrat' },
]

/**
 * Déduit `{ contentType, objectId }` d'un chemin, ou `null`.
 * Pure (aucun accès React) — c'est ce qui la rend testable seule.
 */
export function ficheDepuisChemin(pathname) {
  for (const { motif, contentType } of ROUTES_FICHE) {
    const trouve = motif.exec(pathname || '')
    if (trouve) return { contentType, objectId: Number(trouve[1]) }
  }
  return null
}

/** Message d'indisponibilité : 503 = pas de clé, le reste = erreur réelle. */
function messageIndisponible(erreur) {
  const detail = erreur?.response?.data?.detail
  if (detail) return detail
  return 'Assistant indisponible pour le moment.'
}

export default function CopilotContext({ contentType, objectId }) {
  const dispatch = useDispatch()
  const { pathname } = useLocation()
  const deduite = ficheDepuisChemin(pathname)
  const type = contentType || deduite?.contentType || ''
  const id = objectId ?? deduite?.objectId ?? null

  const [resume, setResume] = useState(null)
  const [resumeErreur, setResumeErreur] = useState('')
  const [actions, setActions] = useState([])
  const [chargement, setChargement] = useState(false)
  const [brouillon, setBrouillon] = useState('')
  const [brouillonErreur, setBrouillonErreur] = useState('')
  const [redaction, setRedaction] = useState(false)

  const charger = useCallback(() => {
    if (!type || !id) return
    setChargement(true)
    setResumeErreur('')
    const corps = { content_type: type, object_id: id }
    // Les deux appels sont INDÉPENDANTS : sans clé LLM le résumé échoue (503)
    // mais les actions, elles, restent disponibles (heuristique serveur).
    Promise.allSettled([
      aiGovernanceApi.resumeFiche(corps),
      aiGovernanceApi.prochainesActions(corps),
    ]).then(([r, a]) => {
      if (r.status === 'fulfilled') setResume(r.value.data)
      else { setResume(null); setResumeErreur(messageIndisponible(r.reason)) }
      setActions(a.status === 'fulfilled' ? (a.value.data?.actions || []) : [])
      setChargement(false)
    })
  }, [type, id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { charger() }, [charger])

  if (!type || !id) return null

  // Cliquer une action NE L'EXÉCUTE PAS : elle part dans l'agent, qui rend sa
  // carte propose → confirme (AG3). L'utilisateur garde la main.
  const lancerAction = (action) => {
    dispatch(queryAgent(
      `${action.label} — ${type} #${id}` +
      (action.action_key ? ` (action ${action.action_key})` : '')))
  }

  const rediger = () => {
    setRedaction(true)
    setBrouillonErreur('')
    aiGovernanceApi.rediger({
      content_type: type, object_id: id, canal: 'email',
    })
      .then((res) => setBrouillon(res.data?.brouillon || ''))
      .catch((err) => setBrouillonErreur(messageIndisponible(err)))
      .finally(() => setRedaction(false))
  }

  return (
    <section
      data-testid="copilot-context"
      className="mb-3 rounded-lg border border-border bg-muted/30 p-3"
    >
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Sparkles className="size-4" aria-hidden="true" />
        Cette fiche
      </h3>

      {chargement && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Analyse en cours…
        </p>
      )}

      {!chargement && resume?.resume && (
        <p className="text-sm text-foreground">{resume.resume}</p>
      )}

      {!chargement && !resume?.resume && resumeErreur && (
        <p className="text-sm text-muted-foreground">{resumeErreur}</p>
      )}

      {actions.length > 0 && (
        <div className="mt-3">
          <h4 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase text-muted-foreground">
            <ListChecks className="size-3.5" aria-hidden="true" />
            Prochaines actions
          </h4>
          <div className="flex flex-col gap-1.5">
            {actions.map((action) => (
              <Button
                key={`${action.action}-${action.priorite}`}
                type="button"
                variant="outline"
                size="sm"
                className="h-auto justify-start whitespace-normal py-1.5 text-left"
                onClick={() => lancerAction(action)}
              >
                <span className="font-medium">{action.label}</span>
                {action.raison && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    — {action.raison}
                  </span>
                )}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={rediger}
          disabled={redaction}
        >
          <PenLine className="size-3.5" aria-hidden="true" />
          Rédiger une réponse
        </Button>
      </div>

      {brouillonErreur && (
        <p className="mt-2 text-sm text-muted-foreground">{brouillonErreur}</p>
      )}

      {brouillon && (
        <div className="mt-2">
          <Textarea
            value={brouillon}
            onChange={(e) => setBrouillon(e.target.value)}
            rows={6}
            aria-label="Brouillon de réponse"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Brouillon éditable — rien n'est envoyé tant que vous ne l'envoyez
            pas vous-même.
          </p>
        </div>
      )}
    </section>
  )
}
