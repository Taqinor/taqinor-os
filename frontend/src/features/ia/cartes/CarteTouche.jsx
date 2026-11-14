import { useEffect, useState } from 'react'
import { Check, Languages, TriangleAlert, Undo2, SkipForward } from 'lucide-react'
import { Button } from '../../../ui'
import iaApi from '../../../api/iaApi'
import crmApi from '../../../api/crmApi'
import { formatDate } from '../../../lib/format'
import { STAGE_LABELS } from '../../crm/stages'
import RelanceEtapeRow from '../../crm/relances/RelanceEtapeRow'
import ToucheMessageDialog from '../../crm/relances/ToucheMessageDialog'
import { traiterGesteTouche } from '../../crm/relances/refusGeste'
import { typeEtape, reponsesDeLEtape } from '../../crm/relances/parcours'
import { lienWhatsAppSur, AGE_MAX_CARTE_MS, GESTES_PROPOSITION } from './cartes'
import { useOuvrirEcran, usePatchCarte, usePreparerTouche, useMajCartesTouche } from './useCarte'

/* COP-F2 — la carte « touche » : on EMBARQUE `RelanceEtapeRow` (l'écran Relances)
   pour hériter de tout — script d'appel, questions à poser, lien `tel:`,
   réponses de la table du parcours, report, saut, refus affichés — avec
   `donnees.touche` (c'est exactement une ligne de `RelanceEtapeSerializer`).
   Le tiroir étroit tient la ligne telle quelle (elle est déjà mobile) ; seul le
   geste « WhatsApp » est repris par la carte (voir `ouvrirWhatsApp`). Aucun
   bouton de la carte n'appelle le modèle. */

// Au-delà de AGE_MAX_CARTE_MS, la touche est RELUE avant d'ouvrir WhatsApp : un
// lead qui a dit STOP entre-temps ne doit pas voir sa conversation s'ouvrir.
const LANGUES_RTL = ['darija', 'ar']

const dateCourte = (iso) => (iso ? formatDate(iso) : '')

function ligneProchaine(prochaine) {
  if (!prochaine) return 'plus aucune touche ouverte pour ce lead'
  const quand = dateCourte(prochaine.due_date)
  return `${prochaine.libelle || 'prochaine touche'}${quand ? ` — ${quand}` : ''}`
}

function EnTete({ lead, touche }) {
  const etape = STAGE_LABELS[lead?.etape] ?? lead?.etape ?? ''
  return (
    <div className="mb-2">
      <p className="text-sm font-semibold">
        {lead?.nom || touche?.lead_nom || 'Lead'}
        {lead?.ville ? <span className="font-normal text-muted-foreground"> · {lead.ville}</span> : null}
      </p>
      <p className="text-xs text-muted-foreground">
        {touche?.libelle}
        {touche?.due_date ? ` · prévue le ${dateCourte(touche.due_date)}` : ''}
        {touche?.canal ? ` · ${touche.canal}` : ''}
        {etape ? ` · ${etape}` : ''}
      </p>
    </div>
  )
}

// Texte VALIDÉ du suivi (rendu par le serveur), droite-à-gauche en darija.
function TexteValide({ message }) {
  if (!message?.message) return null
  const langueTexte = message.repli_langue ? 'fr' : (message.langue ?? 'fr')
  const rtl = LANGUES_RTL.includes(langueTexte)
  return (
    <div
      data-testid="touche-texte"
      className={`whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/40 p-2.5 text-sm${rtl ? ' text-right' : ''}`}
      dir={rtl ? 'rtl' : 'auto'} lang={rtl ? 'ar' : langueTexte}
    >
      {message.message}
    </div>
  )
}

// La proposition du serveur (carte-écho) : UN bouton, le doigt de la commerciale.
function BoutonProposition({ proposition, onEnregistrer, occupe }) {
  if (!proposition || !GESTES_PROPOSITION.includes(proposition.geste)) return null
  return (
    <div className="mt-2.5">
      {/* Le libellé nomme le lead, la touche et la réponse : il passe à la ligne
          DANS le bouton (sur un téléphone il débordait de la carte). */}
      <Button
        className="h-auto min-h-11 w-full whitespace-normal py-2 text-left"
        disabled={occupe} loading={occupe} onClick={onEnregistrer}
      >
        <Check className="size-4 shrink-0" aria-hidden="true" />
        <span className="min-w-0 break-words">Enregistrer : {proposition.libelle}</span>
      </Button>
      {proposition.effet && <p className="mt-1 text-xs text-muted-foreground">{proposition.effet}</p>}
    </div>
  )
}

// Touche traitée : « Fait — prochaine touche : … », Annuler, Touche suivante.
function EtatTraite({ traitee, onAnnuler, onSuivante, occupe, erreur }) {
  const Icone = traitee.geste === 'sauter' ? SkipForward : Check
  return (
    <div data-testid="touche-traitee" className="rounded-lg border border-border bg-background/60 p-2.5 text-sm">
      <p className="flex items-center gap-1.5 font-medium">
        <Icone className="size-4" aria-hidden="true" />
        {traitee.geste === 'sauter' ? 'Sautée' : 'Fait'} — prochaine touche : {ligneProchaine(traitee.prochaine)}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button variant="outline" size="sm" className="min-h-10" disabled={occupe} onClick={onAnnuler}>
          <Undo2 className="size-4" aria-hidden="true" />
          Annuler
        </Button>
        <Button size="sm" className="min-h-10" disabled={occupe} onClick={onSuivante}>
          Touche suivante
        </Button>
      </div>
      {erreur && <p className="mt-2 text-xs text-destructive" role="alert">{erreur}</p>}
    </div>
  )
}

// L'accusé que la table du parcours PROPOSE après cette réponse (ex.
// `ne_plus_contacter` → `stop_contact`), exactement comme la ligne de l'écran
// Relances le propose après son « Confirmer » — ou `null`.
function accuseDeLaReponse(touche, corps) {
  const cle = corps?.reponse
  if (!cle) return null
  const reponse = reponsesDeLEtape(typeEtape(touche), touche).find((r) => r.reponse === cle)
  return reponse?.message || null
}

// Ouvre WhatsApp en UN clic : la fenêtre part dans le geste (les navigateurs
// bloquent une ouverture après une attente) et le journal « WhatsApp ouvert »
// part dans la foulée, sans l'attendre (l'application passe en arrière-plan sur
// Android). RELANCE-WA : cela ne clôt PAS la touche.
function ouvrirEtJournaliser(url, etape, surJournal) {
  window.open(url, '_blank', 'noopener')
  crmApi.whatsappRelanceEtape(etape.id)
    .then((r) => surJournal(r?.data?.etape))
    .catch(() => {})
}

export default function CarteTouche({ carte, index, carteIdx }) {
  const navigate = useOuvrirEcran()
  const patch = usePatchCarte(index, carteIdx)
  // Une réponse, une annulation, un journal : valent pour TOUTES les cartes de
  // la conversation qui portent cette touche (carte « Préparer » + carte-écho).
  const majCartesTouche = useMajCartesTouche()
  const { preparer, occupe: occupeSuivante, erreur: erreurSuivante } = usePreparerTouche()
  const [busyId, setBusyId] = useState(null)
  const [dialogue, setDialogue] = useState(null)
  const [message, setMessage] = useState('')
  const [relecture, setRelecture] = useState(false)
  const donnees = carte.donnees
  const { touche, lead, refus, proposition, proposition_refus: propositionRefus } = donnees
  const traitee = carte.traitee ?? null
  const messageTouche = donnees.message
  const verifieLe = carte.verifie_le ?? carte.recu_le ?? 0

  const relire = async () => {
    setRelecture(true)
    try {
      const res = await iaApi.getToucheAssistant(touche.id)
      patch({ donneesPatch: res.data, verifie_le: Date.now() })
      setMessage('')
      return res.data
    } catch {
      setMessage('Touche impossible à relire pour le moment — vérifiez la connexion.')
      return null
    } finally {
      setRelecture(false)
    }
  }

  // Carte ancienne (ou rejouée de l'historique) : on la relit AVANT de la
  // proposer, pour que le bouton WhatsApp ne rouvre jamais une donnée périmée.
  useEffect(() => {
    if (!traitee && !refus && Date.now() - verifieLe > AGE_MAX_CARTE_MS) queueMicrotask(relire)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- relecture au montage seulement
  }, [])

  // « Reporter » en mode veille rend une AUTRE touche (la reprise) : son message
  // n'est pas celui de l'ancienne — on la relit, sans message entre-temps (le
  // bouton WhatsApp passe alors par la modale, qui rend le bon texte).
  const relireReprise = async (id) => {
    try {
      const res = await iaApi.getToucheAssistant(id)
      majCartesTouche(id, { donneesPatch: res.data, verifie_le: Date.now() })
    } catch {
      setMessage('Touche reprise : relecture impossible pour le moment — le message s’affichera à l’ouverture.')
    }
  }

  const appliquer = (action, ligne) => {
    const nouvelle = ligne?.id ? ligne : touche
    const fini = nouvelle.statut !== 'a_faire'
    const autreTouche = nouvelle.id !== touche.id
    majCartesTouche(touche.id, {
      donneesPatch: {
        touche: nouvelle, proposition: null, proposition_refus: null,
        ...(autreTouche ? { message: null } : {}),
      },
      traitee: fini ? { geste: action, prochaine: ligne?.prochaine_touche ?? null } : null,
    })
    if (autreTouche && !fini) relireReprise(nouvelle.id)
  }

  const traiter = (id, action, payload) => traiterGesteTouche({
    action, id, payload, setBusyId, surSucces: (res) => appliquer(action, res?.data),
  })

  const enregistrerProposition = async () => {
    const corps = proposition.corps ?? {}
    const payload = proposition.geste === 'sauter' ? corps.note : corps
    const accuse = proposition.geste === 'fait' ? accuseDeLaReponse(touche, corps) : null
    try {
      await traiter(touche.id, proposition.geste, payload)
      setMessage('')
      // CAD-A — l'accusé convenu est PROPOSÉ dans la modale d'aperçu (rien ne
      // part sans le clic « Ouvrir WhatsApp »), comme après la ligne.
      if (accuse) setDialogue({ ...touche, message_cle: accuse })
    } catch {
      setMessage('Enregistrement refusé par le serveur — utilisez les réponses ci-dessous.')
    }
  }

  const aOuvrirParLeFlux = () => !refus && messageTouche && touche.statut === 'a_faire'
    && touche.canal === 'whatsapp'
    && lienWhatsAppSur(messageTouche.wa_url) && !messageTouche.crochets?.length
    && !messageTouche.preuve_manquante && !messageTouche.vocal

  const ouvrirWhatsApp = async (etape) => {
    // CAD-A — l'accusé d'une réponse (« stop_contact »…) suit une touche DÉJÀ
    // close : le flux EXACT de l'écran Relances (modale), jamais le message
    // d'origine, et rien n'est journalisé sur la touche.
    if (etape?.message_cle) { setDialogue(etape); return }
    if (touche.statut !== 'a_faire') { setMessage('Touche déjà traitée : rien à ouvrir.'); return }
    // Cas riches (appel, vocal, crochets, e-mail, preuve) : le flux complet de l'écran.
    if (!aOuvrirParLeFlux()) { setDialogue(etape); return }
    if (Date.now() - verifieLe > AGE_MAX_CARTE_MS) {
      const fraiche = await relire()
      if (fraiche && !fraiche.refus) setMessage('Touche relue — appuyez de nouveau sur WhatsApp.')
      return
    }
    ouvrirEtJournaliser(messageTouche.wa_url, etape, (ligne) => {
      if (ligne?.id) majCartesTouche(touche.id, { donneesPatch: { touche: ligne } })
    })
  }

  const annuler = async () => {
    setBusyId(touche.id)
    try {
      const res = await crmApi.annulerRelanceEtape(touche.id)
      majCartesTouche(touche.id, { donneesPatch: { touche: res.data?.id ? res.data : touche }, traitee: null })
      setMessage('')
    } catch {
      setMessage('Annulation impossible (plus de 24 h, ou déjà reprise).')
    } finally {
      setBusyId(null)
    }
  }

  const suivante = async () => {
    const file = await iaApi.getFileTouchesAssistant().then((r) => r.data).catch(() => null)
    const prochaine = (file?.lignes ?? []).find((l) => l.touche_id && l.touche_id !== touche.id)
    if (!file) setMessage('File indisponible pour le moment.')
    else if (!prochaine) setMessage('Plus de touche à faire pour le moment.')
    else await preparer(prochaine.touche_id)
  }

  return (
    <div>
      {/* La ligne embarquée porte déjà le lead, la touche, l'échéance et le canal :
          l'en-tête ne sert que quand elle est absente (refus, touche traitée). */}
      {(refus || traitee) && <EnTete lead={lead} touche={touche} />}
      {refus && (
        <p data-testid="touche-refus" className="flex items-start gap-1.5 text-sm text-destructive" role="alert">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {refus.detail}
        </p>
      )}
      {!refus && <TexteValide message={messageTouche} />}
      {relecture && <p className="mt-2 text-xs text-muted-foreground" role="status">Relecture de la touche…</p>}
      {!refus && !traitee && (
        <BoutonProposition
          proposition={proposition} onEnregistrer={enregistrerProposition} occupe={busyId === touche.id}
        />
      )}
      {!refus && !traitee && propositionRefus && (
        <p data-testid="proposition-refus" className="mt-2 text-xs text-destructive">{propositionRefus}</p>
      )}
      {traitee && (
        <EtatTraite
          traitee={traitee} onAnnuler={annuler} onSuivante={suivante}
          occupe={busyId === touche.id || occupeSuivante} erreur={erreurSuivante || message}
        />
      )}
      {!refus && !traitee && (
        <div className="mt-2.5">
          <RelanceEtapeRow
            etape={touche} busyId={busyId} navigate={navigate} showStatut
            readOnly={touche.statut !== 'a_faire'}
            onFait={(id, payload) => traiter(id, 'fait', payload)}
            onSauter={(id, note) => traiter(id, 'sauter', note)}
            onReporter={(id, rappel) => traiter(id, 'reporter', rappel)}
            onOuvrirMessage={ouvrirWhatsApp}
          />
          {messageTouche && touche.statut === 'a_faire' && (
            <Button variant="ghost" size="sm" className="mt-1 min-h-10" onClick={() => setDialogue(touche)}>
              <Languages className="size-4" aria-hidden="true" />
              Langue et aperçu complet
            </Button>
          )}
        </div>
      )}
      {!traitee && message && <p className="mt-2 text-xs text-muted-foreground" role="status">{message}</p>}
      <ToucheMessageDialog
        etape={dialogue} open={!!dialogue}
        onOpenChange={(o) => { if (!o) setDialogue(null) }}
        onSent={(id, data) => {
          setDialogue(null)
          if (data?.etape?.id) majCartesTouche(data.etape.id, { donneesPatch: { touche: data.etape } })
        }}
      />
    </div>
  )
}
