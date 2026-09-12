// NTSRV30 — Assistant de clôture de ticket SAV (3 étapes).
//
// POURQUOI : la clôture en UN clic laisse partir des tickets sans cause ni
// remède codifiés (XSAV14), sans article KB alors que la panne se répète, et
// sans enquête de satisfaction. Cet assistant rend ces trois gestes VISIBLES
// sans les rendre obligatoires à la création rapide d'un ticket :
//   (1) cause + remède — exigés SEULEMENT ici, jamais à la création ;
//   (2) « Créer un article KB » (optionnel, branche vers NTSRV19) ;
//   (3) canal de résolution + déclenchement de l'enquête (lien share_token
//       déjà existant, FG86/XSAV10).
//
// L'ANCIEN RACCOURCI EST PRÉSERVÉ : « Clôture rapide » ferme le ticket en un
// clic comme aujourd'hui — un agent expert n'est jamais ralenti.
//
// Éléments de formulaire NATIFS (select / checkbox / button) : cet assistant
// doit rester montable partout (inbox NTSRV4, vue détail) sans dépendre d'un
// conteneur de dialogue particulier.
import { useEffect, useState } from 'react'
import kbApi from '../../api/kbApi'
import savApi from '../../api/savApi'

const CANAUX_RESOLUTION = [
  { value: 'a_distance', label: 'À distance' },
  { value: 'sur_site', label: 'Sur site' },
]

/** Message d'erreur serveur lisible, sinon un repli français explicite. */
function messageErreur(erreur, repli) {
  const data = erreur?.response?.data
  if (typeof data === 'string' && data) return data
  if (data?.detail) return data.detail
  const premier = data && typeof data === 'object'
    ? Object.entries(data)[0]
    : null
  if (premier) {
    const [champ, valeur] = premier
    const texte = Array.isArray(valeur) ? valeur[0] : valeur
    return `${champ} : ${texte}`
  }
  return repli
}

export default function TicketClotureWizard({ ticket, onTermine, onAnnuler }) {
  const [etape, setEtape] = useState(1)
  const [causes, setCauses] = useState([])
  const [remedes, setRemedes] = useState([])
  const [cause, setCause] = useState(ticket?.cause ? String(ticket.cause) : '')
  const [remede, setRemede] = useState(
    ticket?.remede ? String(ticket.remede) : '')
  const [creerKb, setCreerKb] = useState(false)
  const [canal, setCanal] = useState(ticket?.canal_resolution || 'sur_site')
  const [enquete, setEnquete] = useState(true)
  const [erreurCause, setErreurCause] = useState('')
  const [erreurRemede, setErreurRemede] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [lienEnquete, setLienEnquete] = useState('')

  useEffect(() => {
    let vivant = true
    Promise.all([
      savApi.getCausesDefaillance(),
      savApi.getRemedesDefaillance(),
    ])
      .then(([repCauses, repRemedes]) => {
        if (!vivant) return
        const liste = (rep) => {
          const data = rep?.data
          return Array.isArray(data) ? data : (data?.results || [])
        }
        setCauses(liste(repCauses))
        setRemedes(liste(repRemedes))
      })
      .catch(() => {
        if (vivant) {
          setErreur('Référentiels cause/remède indisponibles pour le moment.')
        }
      })
    return () => { vivant = false }
  }, [])

  const validerEtape1 = () => {
    // Exigés SEULEMENT à cette étape : la création rapide d'un ticket n'est
    // jamais bloquée par ces deux champs.
    setErreurCause(cause ? '' : 'Choisissez la cause de la panne.')
    setErreurRemede(remede ? '' : 'Choisissez le remède appliqué.')
    if (!cause || !remede) return
    setEtape(2)
  }

  const clotureRapide = async () => {
    setEnCours(true)
    setErreur('')
    try {
      await savApi.cloturerTicket(ticket.id)
      onTermine?.({ rapide: true })
    } catch (e) {
      setErreur(messageErreur(e, 'La clôture a échoué. Réessayez.'))
    } finally {
      setEnCours(false)
    }
  }

  const terminer = async () => {
    setEnCours(true)
    setErreur('')
    try {
      await savApi.updateTicket(ticket.id, {
        cause: Number(cause),
        remede: Number(remede),
        canal_resolution: canal,
      })
      await savApi.cloturerTicket(ticket.id)
      let articleKb = null
      if (creerKb) {
        const rep = await kbApi.creerArticleDepuisTicket({
          ticket_id: ticket.id,
          type_panne: libelle(causes, cause),
          equipement: ticket.equipement_nom || '',
          description: ticket.description || '',
          cause: libelle(causes, cause),
          remede: libelle(remedes, remede),
          derniere_note: ticket.derniere_note || '',
        })
        articleKb = rep?.data || null
      }
      let lien = ''
      if (enquete) {
        const rep = await savApi.lienClientTicket(ticket.id)
        lien = rep?.data?.url || ''
        setLienEnquete(lien)
      }
      onTermine?.({ rapide: false, articleKb, lienEnquete: lien })
    } catch (e) {
      setErreur(messageErreur(e, 'La clôture a échoué. Réessayez.'))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <section aria-label="Assistant de clôture" className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">
          Clôturer {ticket?.reference || 'le ticket'} — étape {etape} sur 3
        </h2>
        <button
          type="button"
          onClick={clotureRapide}
          disabled={enCours}
          className="text-sm underline"
        >
          Clôture rapide
        </button>
      </header>

      {erreur && (
        <p role="alert" className="text-sm text-destructive">{erreur}</p>
      )}

      {etape === 1 && (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Cause de la panne
            <select
              value={cause}
              onChange={(e) => { setCause(e.target.value); setErreurCause('') }}
            >
              <option value="">— Choisir —</option>
              {causes.map((c) => (
                <option key={c.id} value={String(c.id)}>{c.nom}</option>
              ))}
            </select>
          </label>
          {erreurCause && (
            <p role="alert" className="text-sm text-destructive">
              {erreurCause}
            </p>
          )}
          <label className="flex flex-col gap-1 text-sm">
            Remède appliqué
            <select
              value={remede}
              onChange={(e) => {
                setRemede(e.target.value); setErreurRemede('')
              }}
            >
              <option value="">— Choisir —</option>
              {remedes.map((r) => (
                <option key={r.id} value={String(r.id)}>{r.nom}</option>
              ))}
            </select>
          </label>
          {erreurRemede && (
            <p role="alert" className="text-sm text-destructive">
              {erreurRemede}
            </p>
          )}
          <div className="flex gap-2">
            <button type="button" onClick={validerEtape1}>Suivant</button>
            <button type="button" onClick={() => onAnnuler?.()}>Annuler</button>
          </div>
        </div>
      )}

      {etape === 2 && (
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={creerKb}
              onChange={(e) => setCreerKb(e.target.checked)}
            />
            Créer un article KB depuis ce ticket
          </label>
          <p className="text-xs text-muted-foreground">
            L'article part en brouillon, pré-rempli avec la cause et le
            remède saisis : vous le relisez et le publiez ensuite.
          </p>
          <div className="flex gap-2">
            <button type="button" onClick={() => setEtape(1)}>Précédent</button>
            <button type="button" onClick={() => setEtape(3)}>Suivant</button>
          </div>
        </div>
      )}

      {etape === 3 && (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Canal de résolution
            <select value={canal} onChange={(e) => setCanal(e.target.value)}>
              {CANAUX_RESOLUTION.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enquete}
              onChange={(e) => setEnquete(e.target.checked)}
            />
            Envoyer l'enquête de satisfaction au client
          </label>
          {lienEnquete && (
            <code className="break-all text-xs text-muted-foreground">
              {lienEnquete}
            </code>
          )}
          <div className="flex gap-2">
            <button type="button" onClick={() => setEtape(2)}>Précédent</button>
            <button type="button" onClick={terminer} disabled={enCours}>
              Clôturer le ticket
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

/** Libellé d'un référentiel à partir de son id (chaîne), ou ''. */
function libelle(liste, id) {
  const trouve = liste.find((item) => String(item.id) === String(id))
  return trouve?.nom || ''
}
