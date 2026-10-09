// NTSRV16/NTSRV17/NTSRV31 — Gestion Problème (Problem Management).
//
// Un « problème » regroupe N tickets qui partagent UNE cause racine (ex.
// « Onduleur X — Surchauffe », 12 tickets). L'écran montre :
//   * les PROBLÈMES existants, triés par impact (nb tickets × ancienneté,
//     calculé côté serveur) ;
//   * les REGROUPEMENTS SUGGÉRÉS (NTSRV17) — jamais créés automatiquement.
//
// NTSRV31 — l'assistant en 2 étapes remplace le « clic simple » : l'agent voit
// le regroupement pré-rempli et DÉCOCHE ce qui n'en fait pas partie, puis
// confirme ; la création + le rattachement partent en UN SEUL appel
// transactionnel (`creer-depuis-regroupement`), donc jamais un problème créé
// à moitié rattaché.
import { useEffect, useState } from 'react'
import savApi from '../../api/savApi'

const STATUT_LABELS = {
  identifie: 'Identifié',
  en_analyse: 'En analyse',
  resolu: 'Résolu',
}

/** Message serveur lisible, sinon un repli français explicite. */
function messageErreur(erreur, repli) {
  const data = erreur?.response?.data
  if (data?.detail) return data.detail
  const premier = data && typeof data === 'object' ? Object.entries(data)[0] : null
  if (premier) {
    const [champ, valeur] = premier
    return Array.isArray(valeur) ? `${champ} : ${valeur[0]}` : `${champ} : ${valeur}`
  }
  return repli
}

const liste = (reponse) => {
  const data = reponse?.data
  if (Array.isArray(data)) return data
  return data?.results || []
}

export default function ProblemesPage() {
  const [problemes, setProblemes] = useState([])
  const [groupes, setGroupes] = useState([])
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')

  // Assistant NTSRV31 (null = fermé).
  const [assistant, setAssistant] = useState(null)
  const [etape, setEtape] = useState(1)
  const [titre, setTitre] = useState('')
  const [causeRacine, setCauseRacine] = useState('')
  const [coches, setCoches] = useState([])
  const [erreurTitre, setErreurTitre] = useState('')
  const [enCours, setEnCours] = useState(false)

  // ASAV55 — gestion d'UN problème : tickets liés, liaison / déliaison,
  // résolution avec cause racine, suppression confirmée.
  const [selection, setSelection] = useState(null) // problème ouvert
  const [ticketsLies, setTicketsLies] = useState([])
  const [ticketALier, setTicketALier] = useState('')
  const [statutEdit, setStatutEdit] = useState('identifie')
  const [causeEdit, setCauseEdit] = useState('')
  const [confirmSuppr, setConfirmSuppr] = useState(false)
  const [occupe, setOccupe] = useState(false)

  const charger = () => {
    setChargement(true)
    Promise.all([
      savApi.getProblemes({ ordering: '-impact' }),
      savApi.getRegroupementsSuggeres(),
    ])
      .then(([repProblemes, repGroupes]) => {
        setProblemes(liste(repProblemes))
        setGroupes(repGroupes?.data?.results || [])
      })
      .catch(() => setErreur('Chargement impossible pour le moment.'))
      .finally(() => setChargement(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { charger() }, [])

  const chargerTicketsLies = (id) => savApi.getProblemeTickets(id)
    .then((rep) => setTicketsLies(liste(rep)))
    .catch(() => setErreur('Tickets du problème indisponibles pour le moment.'))

  const ouvrirProbleme = (probleme) => {
    setSelection(probleme)
    setStatutEdit(probleme.statut || 'identifie')
    setCauseEdit(probleme.cause_racine || '')
    setTicketALier('')
    setConfirmSuppr(false)
    setErreur('')
    chargerTicketsLies(probleme.id)
  }

  const lierTicket = async () => {
    const numero = Number(ticketALier)
    if (!numero) return
    setOccupe(true)
    setErreur('')
    try {
      await savApi.lierTicketProbleme(selection.id, numero)
      setTicketALier('')
      await chargerTicketsLies(selection.id)
      charger()
    } catch (e) {
      setErreur(messageErreur(e, 'Le rattachement du ticket a échoué.'))
    } finally { setOccupe(false) }
  }

  const delierTicket = async (ticketId) => {
    setOccupe(true)
    setErreur('')
    try {
      await savApi.delierTicketProbleme(selection.id, ticketId)
      await chargerTicketsLies(selection.id)
      charger()
    } catch (e) {
      setErreur(messageErreur(e, 'Le détachement du ticket a échoué.'))
    } finally { setOccupe(false) }
  }

  const enregistrerProbleme = async () => {
    setOccupe(true)
    setErreur('')
    try {
      const rep = await savApi.saveProbleme(selection.id, {
        statut: statutEdit, cause_racine: causeEdit,
      })
      setSelection((s) => ({ ...s, ...(rep?.data ?? {}), statut: statutEdit, cause_racine: causeEdit }))
      charger()
    } catch (e) {
      setErreur(messageErreur(e, "L'enregistrement du problème a échoué."))
    } finally { setOccupe(false) }
  }

  const supprimerProbleme = async () => {
    setOccupe(true)
    setErreur('')
    try {
      await savApi.deleteProbleme(selection.id)
      setSelection(null)
      setConfirmSuppr(false)
      charger()
    } catch (e) {
      setErreur(messageErreur(e, 'La suppression du problème a échoué.'))
    } finally { setOccupe(false) }
  }

  const ouvrirAssistant = (groupe) => {
    setAssistant(groupe)
    setEtape(1)
    setTitre(groupe.titre_suggere || '')
    setCauseRacine('')
    // Tous les tickets du regroupement sont COCHÉS par défaut ; décocher en
    // exclut réellement (c'est le critère d'acceptation de NTSRV31).
    setCoches(groupe.tickets.map((t) => t.id))
    setErreurTitre('')
    setErreur('')
  }

  const basculer = (id) => {
    setCoches((actuels) => actuels.includes(id)
      ? actuels.filter((valeur) => valeur !== id)
      : [...actuels, id])
  }

  const validerEtape1 = () => {
    if (!titre.trim()) {
      setErreurTitre('Donnez un titre au problème.')
      return
    }
    if (coches.length === 0) {
      setErreur('Cochez au moins un ticket à rattacher.')
      return
    }
    setErreurTitre('')
    setErreur('')
    setEtape(2)
  }

  const creer = async () => {
    setEnCours(true)
    setErreur('')
    try {
      await savApi.creerProblemeDepuisRegroupement({
        titre: titre.trim(),
        cause_racine: causeRacine,
        ticket_ids: coches,
      })
      setAssistant(null)
      charger()
    } catch (e) {
      setErreur(messageErreur(e, 'La création du problème a échoué.'))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="ui-root mx-auto flex max-w-5xl flex-col gap-5 p-1">
      <header>
        <h1 className="font-display text-2xl font-bold tracking-tight">
          Problèmes
        </h1>
        <p className="text-sm text-muted-foreground">
          {problemes.length} problème{problemes.length > 1 ? 's' : ''} suivi
          {problemes.length > 1 ? 's' : ''}
        </p>
      </header>

      {erreur && (
        <p role="alert" className="text-sm text-destructive">{erreur}</p>
      )}

      {assistant ? (
        <section aria-label="Assistant de création de problème"
                 className="flex flex-col gap-3 rounded-md border border-border p-4">
          <h2 className="text-base font-semibold">
            Créer un problème — étape {etape} sur 2
          </h2>

          {etape === 1 && (
            <div className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-sm">
                Titre du problème
                <input
                  type="text"
                  value={titre}
                  onChange={(e) => { setTitre(e.target.value); setErreurTitre('') }}
                />
              </label>
              {erreurTitre && (
                <p role="alert" className="text-sm text-destructive">
                  {erreurTitre}
                </p>
              )}
              <label className="flex flex-col gap-1 text-sm">
                Cause racine (facultatif)
                <textarea
                  value={causeRacine}
                  onChange={(e) => setCauseRacine(e.target.value)}
                />
              </label>
              <fieldset className="flex flex-col gap-2">
                <legend className="text-sm font-medium">
                  Tickets à rattacher ({coches.length} sur{' '}
                  {assistant.tickets.length})
                </legend>
                {assistant.tickets.map((ticket) => (
                  <label key={ticket.id}
                         className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={coches.includes(ticket.id)}
                      onChange={() => basculer(ticket.id)}
                    />
                    {ticket.reference}
                    {ticket.client ? ` — ${ticket.client}` : ''}
                  </label>
                ))}
              </fieldset>
              <div className="flex gap-2">
                <button type="button" onClick={validerEtape1}>Suivant</button>
                <button type="button" onClick={() => setAssistant(null)}>
                  Annuler
                </button>
              </div>
            </div>
          )}

          {etape === 2 && (
            <div className="flex flex-col gap-3">
              <p className="text-sm">
                « {titre} » sera créé avec {coches.length} ticket
                {coches.length > 1 ? 's' : ''} rattaché
                {coches.length > 1 ? 's' : ''}.
              </p>
              <p className="text-xs text-muted-foreground">
                Les tickets gardent leur propre statut : résoudre le problème
                n'en clôture aucun.
              </p>
              <div className="flex gap-2">
                <button type="button" onClick={() => setEtape(1)}>
                  Précédent
                </button>
                <button type="button" onClick={creer} disabled={enCours}>
                  Créer le problème
                </button>
              </div>
            </div>
          )}
        </section>
      ) : (
        <section aria-label="Regroupements suggérés"
                 className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">Regroupements suggérés</h2>
          {groupes.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucun regroupement suggéré : aucun produit n'accumule assez de
              tickets sur la même cause.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {groupes.map((groupe) => (
                <li key={`${groupe.produit_id}-${groupe.cause_id}`}
                    className="flex items-center justify-between gap-3 rounded-md border border-border p-3">
                  <span className="text-sm">
                    {groupe.titre_suggere} — {groupe.nb_tickets} tickets
                  </span>
                  <button type="button" onClick={() => ouvrirAssistant(groupe)}>
                    Créer le problème
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {selection && (
        <section aria-label={`Problème ${selection.reference}`}
                 className="flex flex-col gap-3 rounded-md border border-border p-4">
          <h2 className="text-base font-semibold">
            {selection.reference} — {selection.titre}
          </h2>

          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">
              Tickets liés ({ticketsLies.length})
            </span>
            {ticketsLies.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun ticket lié.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {ticketsLies.map((t) => (
                  <li key={t.id} className="flex items-center gap-2 text-sm">
                    <span>{t.reference}{t.client ? ` — ${t.client}` : ''}</span>
                    <button type="button" disabled={occupe}
                            onClick={() => delierTicket(t.id)}>
                      Délier {t.reference}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex items-center gap-2">
              <input type="number" placeholder="N° du ticket à lier" aria-label="N° du ticket à lier"
                     value={ticketALier} onChange={(e) => setTicketALier(e.target.value)} />
              <button type="button" disabled={occupe || !ticketALier} onClick={lierTicket}>
                Lier un ticket
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-1 text-sm">
              Statut du problème
              <select value={statutEdit} onChange={(e) => setStatutEdit(e.target.value)}>
                {Object.entries(STATUT_LABELS).map(([valeur, nom]) => (
                  <option key={valeur} value={valeur}>{nom}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Cause racine
              <textarea value={causeEdit} onChange={(e) => setCauseEdit(e.target.value)} />
            </label>
            <div className="flex gap-2">
              <button type="button" disabled={occupe} onClick={enregistrerProbleme}>
                Enregistrer le problème
              </button>
              <button type="button" onClick={() => setSelection(null)}>Fermer</button>
            </div>
          </div>

          {ticketsLies.length === 0 && (
            confirmSuppr ? (
              <div className="flex items-center gap-2 text-sm">
                <span>Supprimer définitivement {selection.reference} ?</span>
                <button type="button" disabled={occupe} onClick={supprimerProbleme}>
                  Confirmer la suppression
                </button>
                <button type="button" onClick={() => setConfirmSuppr(false)}>Annuler</button>
              </div>
            ) : (
              <button type="button" className="self-start" onClick={() => setConfirmSuppr(true)}>
                Supprimer ce problème
              </button>
            )
          )}
        </section>
      )}

      <section aria-label="Problèmes suivis" className="flex flex-col gap-2">
        <h2 className="text-base font-semibold">Problèmes suivis</h2>
        {chargement ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : problemes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun problème ouvert.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">Référence</th>
                <th className="text-left">Titre</th>
                <th className="text-left">Statut</th>
                <th className="text-left">Tickets</th>
                <th className="text-left">Impact</th>
                <th className="text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {problemes.map((probleme) => (
                <tr key={probleme.id}>
                  <td>{probleme.reference}</td>
                  <td>{probleme.titre}</td>
                  <td>
                    {probleme.statut_display
                      || STATUT_LABELS[probleme.statut]
                      || probleme.statut}
                  </td>
                  <td>{probleme.nb_tickets}</td>
                  <td>{probleme.impact}</td>
                  <td>
                    <button type="button" onClick={() => ouvrirProbleme(probleme)}>
                      Gérer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
