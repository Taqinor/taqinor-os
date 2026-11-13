import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Languages, TriangleAlert, Undo2, SkipForward } from 'lucide-react'
import { Button } from '../../../ui'
import iaApi from '../../../api/iaApi'
import crmApi from '../../../api/crmApi'
import { formatDate } from '../../../lib/format'
import { STAGE_LABELS } from '../../crm/stages'
import RelanceEtapeRow from '../../crm/relances/RelanceEtapeRow'
import ToucheMessageDialog from '../../crm/relances/ToucheMessageDialog'
import { traiterGesteTouche } from '../../crm/relances/refusGeste'
import { lienWhatsAppSur, AGE_MAX_CARTE_MS, GESTES_PROPOSITION } from './cartes'
import { usePatchCarte, usePreparerTouche } from './useCarte'

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
      <Button className="min-h-11 w-full" disabled={occupe} loading={occupe} onClick={onEnregistrer}>
        <Check className="size-4" aria-hidden="true" />
        Enregistrer : {proposition.libelle}
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
  const navigate = useNavigate()
  const patch = usePatchCarte(index, carteIdx)
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

  const appliquer = (action, ligne) => {
    const nouvelle = ligne?.id ? ligne : touche
    const fini = nouvelle.statut !== 'a_faire'
    patch({
      donneesPatch: { touche: nouvelle, proposition: null, proposition_refus: null },
      traitee: fini ? { geste: action, prochaine: ligne?.prochaine_touche ?? null } : null,
    })
  }

  const traiter = (id, action, payload) => traiterGesteTouche({
    action, id, payload, setBusyId, surSucces: (res) => appliquer(action, res?.data),
  })

  const enregistrerProposition = async () => {
    const corps = proposition.corps ?? {}
    const payload = proposition.geste === 'sauter' ? corps.note : corps
    try {
      await traiter(touche.id, proposition.geste, payload)
      setMessage('')
    } catch {
      setMessage('Enregistrement refusé par le serveur — utilisez les réponses ci-dessous.')
    }
  }

  const aOuvrirParLeFlux = () => !refus && messageTouche && touche.canal === 'whatsapp'
    && lienWhatsAppSur(messageTouche.wa_url) && !messageTouche.crochets?.length
    && !messageTouche.preuve_manquante && !messageTouche.vocal

  const ouvrirWhatsApp = async (etape) => {
    // Cas riches (appel, vocal, crochets, e-mail, preuve) : le flux complet de l'écran.
    if (!aOuvrirParLeFlux()) { setDialogue(etape); return }
    if (Date.now() - verifieLe > AGE_MAX_CARTE_MS) {
      const fraiche = await relire()
      if (fraiche) setMessage('Touche relue — appuyez de nouveau sur WhatsApp.')
      return
    }
    ouvrirEtJournaliser(messageTouche.wa_url, etape, (ligne) => {
      if (ligne?.id) patch({ donneesPatch: { touche: ligne } })
    })
  }

  const annuler = async () => {
    setBusyId(touche.id)
    try {
      const res = await crmApi.annulerRelanceEtape(touche.id)
      patch({ donneesPatch: { touche: res.data?.id ? res.data : touche }, traitee: null })
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
          {messageTouche && (
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
          if (data?.etape?.id) patch({ donneesPatch: { touche: data.etape } })
        }}
      />
    </div>
  )
}
