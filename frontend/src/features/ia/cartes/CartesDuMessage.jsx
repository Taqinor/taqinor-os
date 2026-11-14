import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { CheckCircle2, ShieldQuestion, Check, X, Clock, Ban, TriangleAlert } from 'lucide-react'
import { Button, buttonVariants } from '../../../ui'
import { cn } from '../../../lib/cn'
import { confirmAgentAction, dismissProposal } from '../store/iaSlice'
import { ETATS, etatAffiche, lienWhatsAppSur } from './cartes'
import CarteTouche from './CarteTouche'
import {
  CarteFileTouches, CarteMatin, CarteListeLeads, CarteFicheLead, CarteSuiteTouche,
} from './CartesCrm'
import {
  CarteWaMessage, CarteWaDevis, CarteDocument, CarteVisite,
} from './CartesWhatsApp'
import CarteDiagnostic from './CarteDiagnostic'

/* COP-F1 — le rendu des cartes d'un message agent, dans l'ordre du serveur.
   Une carte ne vient JAMAIS du texte du modèle : seul `msg.cartes` est lu.
   Les cartes vivent ici (`features/ia/cartes/`) et servent au tiroir Copilote
   comme à la page `/ia/agent`, sans copie. Seuls `testId` et la marge varient. */

// Identifiants de test et padding par surface.
const VARIANTES = {
  copilot: { proposition: 'copilot-proposal-card', resultat: 'copilot-result-card', pad: 'p-2.5' },
  page: { proposition: 'proposal-card', resultat: 'result-card', pad: 'p-3' },
}

const CLASSE_PROPOSITION = 'mt-2 rounded-md border border-amber-500/40 bg-amber-500/10 text-foreground'
const CLASSE_RESULTAT = 'mt-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 text-foreground'

// Carte « Action effectuée » générique (carte `null` ou inconnue). N'ouvre un lien
// WhatsApp que s'il est sûr (https://wa.me/ ou api.whatsapp.com) ; jamais de
// lien de devis construit depuis un `id` quelconque.
function CarteGenerique({ carte, testId, className }) {
  const donnees = carte.donnees ?? {}
  const reference = donnees.reference ?? donnees.numero ?? ''
  const wa = lienWhatsAppSur(donnees.wa_url)
  return (
    <div data-testid={testId} className={className}>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 className="size-3.5" aria-hidden="true" />
        Action effectuée
      </p>
      {carte.libelle && <p className="mt-1 text-sm">{carte.libelle}</p>}
      {reference && (
        <p className="mt-1.5 text-sm">
          Référence : <span className="font-medium">{reference}</span>
        </p>
      )}
      {wa && (
        <a
          href={wa} target="_blank" rel="noopener noreferrer"
          className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'mt-2.5 min-h-10')}
        >
          Ouvrir WhatsApp
        </a>
      )}
    </div>
  )
}

const COMPOSANTS = {
  touche: CarteTouche,
  suite_touche: CarteSuiteTouche,
  file_touches: CarteFileTouches,
  matin: CarteMatin,
  liste_leads: CarteListeLeads,
  fiche_lead: CarteFicheLead,
  wa_message: CarteWaMessage,
  wa_devis: CarteWaDevis,
  document: CarteDocument,
  visite: CarteVisite,
  diagnostic: CarteDiagnostic,
}

// Aiguille une carte « résultat » par sa clé `carte`.
export function CarteResultat({ carte, index, carteIdx, variant = 'page' }) {
  const v = VARIANTES[variant] ?? VARIANTES.page
  const Composant = COMPOSANTS[carte.carte]
  const className = `${CLASSE_RESULTAT} ${v.pad}`
  if (!Composant) {
    return <CarteGenerique carte={carte} testId={v.resultat} className={className} />
  }
  return (
    <div className={className} data-testid={`carte-${carte.carte}`}>
      <Composant carte={carte} index={index} carteIdx={carteIdx} variant={variant} />
    </div>
  )
}

// Renvoie le « maintenant » de l'écran et le rafraîchit à l'échéance de la
// proposition : une carte laissée ouverte devient « expirée » sans qu'on la touche.
function useMaintenant(echeance) {
  const [maintenant, setMaintenant] = useState(() => Date.now())
  useEffect(() => {
    if (!echeance) return undefined
    const reste = echeance - Date.now()
    if (reste <= 0) return undefined
    // setTimeout plafonné : un délai > ~24 j déborderait.
    const t = setTimeout(() => setMaintenant(Date.now()), Math.min(reste + 50, 2 ** 31 - 1))
    return () => clearTimeout(t)
  }, [echeance])
  return maintenant
}

const ETAT_TEXTE = {
  [ETATS.EXPIREE]: ['Proposition expirée — redemandez-la à l’assistant.', Clock],
  [ETATS.ANNULEE]: ['Proposition annulée.', Ban],
}

// Carte « proposition » : chacune a SON état. Le doigt de la commerciale
// confirme (jamais la voix, jamais le modèle) ; le jeton ne sert qu'une fois.
export function CarteProposition({ carte, index, carteIdx, variant = 'page' }) {
  const dispatch = useDispatch()
  const v = VARIANTES[variant] ?? VARIANTES.page
  const maintenant = useMaintenant(carte.expire_le)
  const etat = etatAffiche(carte, maintenant)
  const enCours = etat === ETATS.EN_COURS
  const className = `${CLASSE_PROPOSITION} ${v.pad}`
  const [texte, Icone] = ETAT_TEXTE[etat] ?? []
  return (
    <div data-testid={v.proposition} data-etat={etat} className={className}>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
        <ShieldQuestion className="size-3.5" aria-hidden="true" />
        {etat === ETATS.CONFIRMEE ? 'Confirmée' : 'Confirmation requise'}
      </p>
      {(carte.apercu || carte.libelle) && (
        <p className="mt-1.5 whitespace-pre-wrap break-words text-sm">{carte.apercu || carte.libelle}</p>
      )}
      {texte && (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
          <Icone className="size-3.5" aria-hidden="true" />
          {texte}
        </p>
      )}
      {(etat === ETATS.A_CONFIRMER || enCours) && !carte.confirm_token && (
        <p className="mt-1.5 text-xs text-muted-foreground">Confirmation indisponible pour le moment.</p>
      )}
      {(etat === ETATS.A_CONFIRMER || enCours) && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          <Button
            size="sm" className="min-h-10 flex-1"
            disabled={!carte.confirm_token || enCours} loading={enCours}
            onClick={() => dispatch(confirmAgentAction({ token: carte.confirm_token, index, carte: carteIdx }))}
          >
            <Check className="size-4" aria-hidden="true" />
            Confirmer
          </Button>
          <Button
            variant="outline" size="sm" className="min-h-10" disabled={enCours}
            onClick={() => dispatch(dismissProposal({ index, carte: carteIdx }))}
          >
            <X className="size-4" aria-hidden="true" />
            Annuler
          </Button>
        </div>
      )}
      {carte.erreur && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-destructive" role="alert">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {carte.erreur}
        </p>
      )}
      {etat === ETATS.CONFIRMEE && carte.resultat && (
        <CarteResultat carte={carte.resultat} variant={variant} />
      )}
    </div>
  )
}

/** Toutes les cartes d'un message, dans l'ordre. */
export default function CartesDuMessage({ msg, index, variant }) {
  if (!Array.isArray(msg?.cartes) || msg.cartes.length === 0) return null
  return msg.cartes.map((carte, i) => (carte.type === 'proposition'
    ? <CarteProposition key={i} carte={carte} index={index} carteIdx={i} variant={variant} />
    : <CarteResultat key={i} carte={carte} index={index} carteIdx={i} variant={variant} />))
}
