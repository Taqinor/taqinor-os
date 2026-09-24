import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Button, Card, Spinner } from '../../../ui'

/* ============================================================================
   CALX349 — L'ONGLET « APPROBATION » DE L'ATELIER.
   ----------------------------------------------------------------------------
   LE TROU QU'IL BOUCHE. Le module n'avait que deux codes de permission
   (`calepinage_voir`, `calepinage_gerer`) : « qui peut écrire » valait « qui
   peut valider ». CALX347 a créé le troisième code, `calepinage_approuver`,
   et la porte `GET/POST calepinages/<pk>/approbation/` (contrat CALX334,
   `contract_samples/calepinage_approbation.json`) ; ce panneau en est le
   PREMIER et SEUL lecteur/décideur.

   AUCUN SECOND CALCUL ICI : l'état (`etat`, `decide_par`, `decide_le`,
   `motif`, `exigee`) est RECOPIÉ tel que le serveur le sert. La décision
   (`decision`, `motif`) est envoyée telle quelle ; la réponse du POST
   remplace l'état affiché SANS second appel (le contrat le garantit).

   DROITS : sans le code `calepinage_approuver`, les boutons Approuver/Refuser
   sont ABSENTS et la raison est affichée (jamais un bouton désactivé muet).
   Un refus serveur (mauvais code, décision inconnue, refus sans motif, ou
   une suggestion d'origine automatique encore en attente — CALX106/CALX29)
   est un 400 qui NOMME son champ : le bandeau liste les champs fautifs et le
   message SERVEUR est rendu SOUS le champ concerné (règle fondateur du
   08/09/2026) — jamais un « refus » générique.
   ========================================================================== */

const LIBELLE_DECISION = { approuve: 'Approuvée', refuse: 'Refusée' }

/** Un horodatage ISO, mis en forme humainement ; brut si non parsable. */
function formaterDate(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('fr-FR')
}

/** Les clés d'erreur qui NE SONT PAS `decision`/`motif`/`detail` : ce sont
    les suggestions automatiques en attente, chacune sous son chemin de
    document (`buildings[0].hauteurM`) — contrat `refus_suggestions_en_attente`. */
function suggestionsEnAttente(erreurs) {
  return Object.keys(erreurs).filter((champ) => !['decision', 'motif', 'detail'].includes(champ))
}

export default function Approbation({ calepinageId: idPropose = null }) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl ?? null
  const peutApprouver = useHasPermission('calepinage_approuver')

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.approbation(calepinageId),
    calepinageId,
    {
      select: (reponse) => reponse?.data ?? null,
      enabled: Boolean(calepinageId),
      errorMessage: 'L’état d’approbation n’a pas pu être chargé.',
    },
  )

  const [motif, setMotif] = useState('')
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState(false)
  // Le POST rend DÉJÀ l'état à jour (contrat CALX334) : cette valeur PREND LE
  // PAS sur `data` une fois posée, pour qu'AUCUN second appel de lecture ne
  // soit nécessaire après une décision — remise à zéro si on change de
  // calepinage (patron React : ajuster l'état PENDANT le rendu, jamais dans
  // un effet, pour une réinitialisation dérivée d'une prop).
  const [etatDecide, setEtatDecide] = useState(null)
  const [idDeEtatDecide, setIdDeEtatDecide] = useState(calepinageId)
  if (idDeEtatDecide !== calepinageId) {
    setIdDeEtatDecide(calepinageId)
    setEtatDecide(null)
  }

  const decider = (decision) => {
    if (!calepinageId) return
    setErreurs({})
    setEnCours(true)
    Promise.resolve(calepinageApi.calepinages.decisionApprobation(calepinageId, { decision, motif }))
      .then((reponse) => {
        setEtatDecide(reponse?.data ?? null)
        setMotif('')
      })
      .catch((err) => {
        const corps = err?.response?.data
        setErreurs(corps && typeof corps === 'object'
          ? corps
          : { detail: 'La décision a été refusée par le serveur.' })
      })
      .finally(() => setEnCours(false))
  }

  if (loading) return <Spinner />
  if (error) {
    return (
      <p className="text-sm text-destructive" role="alert" data-testid="calx349-erreur">{error}</p>
    )
  }
  const etat = etatDecide ?? data
  if (!etat) return null

  const champsFautifs = Object.keys(erreurs)
  const enAttente = suggestionsEnAttente(erreurs)

  return (
    <div className="space-y-4" data-testid="calx349-panneau">
      <Card className="p-4" data-testid="calx349-etat">
        <h3 className="text-sm font-semibold">Approbation</h3>
        {etat.exigee && (
          <p className="mt-1 text-xs text-muted-foreground" data-testid="calx349-exigee">
            Une approbation est exigée avant de retenir une variante (réglage société).
          </p>
        )}
        {etat.etat ? (
          <p className="mt-2 text-sm" data-testid="calx349-decision">
            {LIBELLE_DECISION[etat.etat] || etat.etat}
            {etat.decide_par?.nom_complet ? ` par ${etat.decide_par.nom_complet}` : ''}
            {etat.decide_le ? ` le ${formaterDate(etat.decide_le)}` : ''}
          </p>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground" data-testid="calx349-aucune-decision">
            Aucune décision n’a encore été prise.
          </p>
        )}
        {etat.motif && (
          <p className="mt-1 text-xs text-muted-foreground" data-testid="calx349-motif-decision">
            Motif : {etat.motif}
          </p>
        )}
      </Card>

      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="calx349-bandeau"
          className="rounded border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          {`Décision refusée — à corriger : ${champsFautifs.join(', ')}`}
        </p>
      )}

      {enAttente.length > 0 && (
        <ul className="space-y-1" data-testid="calx349-suggestions-en-attente">
          {enAttente.map((champ) => (
            <li key={champ} className="text-xs text-red-300" data-testid={`calx349-suggestion-${champ}`}>
              <strong>{champ}</strong> — {erreurs[champ]}
            </li>
          ))}
        </ul>
      )}

      {peutApprouver ? (
        <Card className="p-4" data-testid="calx349-decider">
          <label className="block" data-testid="calx349-champ-motif">
            <span className="text-xs text-muted-foreground">
              Motif (obligatoire pour un refus)
            </span>
            <textarea
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              className="mt-1 w-full rounded border border-input bg-card px-2 py-1 text-sm"
            />
          </label>
          {erreurs.motif && (
            <p role="alert" data-testid="calx349-erreur-motif" className="mt-1 text-xs text-red-300">
              {erreurs.motif}
            </p>
          )}
          {erreurs.decision && (
            <p role="alert" data-testid="calx349-erreur-decision" className="mt-1 text-xs text-red-300">
              {erreurs.decision}
            </p>
          )}
          <div className="mt-3 flex gap-2">
            <Button
              type="button"
              variant="success"
              disabled={enCours}
              onClick={() => decider('approuve')}
              data-testid="calx349-approuver"
            >
              Approuver
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={enCours}
              onClick={() => decider('refuse')}
              data-testid="calx349-refuser"
            >
              Refuser
            </Button>
          </div>
        </Card>
      ) : (
        <p className="text-xs text-muted-foreground" data-testid="calx349-sans-droit">
          Vous n’avez pas le code « calepinage_approuver » : seule la lecture est possible.
        </p>
      )}
    </div>
  )
}
