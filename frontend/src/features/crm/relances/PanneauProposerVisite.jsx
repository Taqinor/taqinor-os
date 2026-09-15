// VISCAD — Panneau de coaching « Proposer la visite », la couche manquante
// de la cadence après-devis (fondateur 15/09/2026) : QUAND et COMMENT
// proposer la visite technique, rendu à côté de la touche actionnable
// ('apres_devis' uniquement — la visite se propose en RÉPONSE au devis
// envoyé, jamais en prise de contact/réveil). Compact et repliable par
// défaut : un coup d'œil sur la phase, un clic pour le détail.
import { useState } from 'react'
import { MapPin, ChevronDown, ChevronRight, MessageCircle } from 'lucide-react'
import { Button, Badge } from '../../../ui'
import {
  phaseVisite, PHASE_GUIDANCE, SIGNAUX_ACHAT, REGLE_OBJECTION,
  REGLE_VRAI_CLIENT,
} from './visiteGuidance'
import MessageVisiteDialog from './MessageVisiteDialog'

const PHASE_TONE = { 1: 'neutral', 2: 'info', 3: 'primary' }

export default function PanneauProposerVisite({ etape, onPlanifier }) {
  const [ouvert, setOuvert] = useState(false)
  const [messageOuvert, setMessageOuvert] = useState(false)

  if (!etape || etape.cadence !== 'apres_devis') return null

  const phase = phaseVisite(etape)
  const guidance = PHASE_GUIDANCE[phase]
  const telephone = etape.lead_whatsapp || etape.lead_telephone

  return (
    <div className="mt-1.5 rounded-md border border-dashed border-border p-2" data-testid="panneau-proposer-visite">
      <button
        type="button"
        className="flex w-full items-center gap-1.5 text-left text-xs font-medium text-foreground"
        aria-expanded={ouvert}
        onClick={() => setOuvert((v) => !v)}
      >
        {ouvert ? <ChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
          : <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" />}
        <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
        <span>Proposer la visite</span>
        <Badge tone={PHASE_TONE[phase] ?? 'neutral'}>{guidance.titre}</Badge>
      </button>
      {ouvert && (
        <div className="mt-2 flex flex-col gap-2 text-xs text-muted-foreground">
          <p>{guidance.texte}</p>
          {guidance.script && (
            <p className="rounded-md bg-muted/40 p-2 italic">
              « {guidance.script} »
              {guidance.jamais && <span className="not-italic"> — {guidance.jamais}</span>}
            </p>
          )}
          <div>
            <p className="font-medium text-foreground">
              Signaux d&apos;achat = proposez tout de suite
            </p>
            <ul className="ml-4 list-disc">
              {SIGNAUX_ACHAT.map((s) => <li key={s}>{s}</li>)}
            </ul>
          </div>
          <p className="font-medium text-foreground">{REGLE_OBJECTION}</p>
          <p className="font-medium text-foreground">{REGLE_VRAI_CLIENT}</p>
          <div className="flex flex-wrap justify-end gap-1.5">
            <Button
              type="button" size="sm" variant="outline"
              onClick={() => setMessageOuvert(true)}
            >
              <MessageCircle className="size-3.5" /> Message visite prêt
            </Button>
            <Button type="button" size="sm" onClick={() => onPlanifier?.()}>
              Client d&apos;accord → Planifier la visite
            </Button>
          </div>
        </div>
      )}
      <MessageVisiteDialog
        leadId={etape.lead}
        telephone={telephone}
        cle="visite_proposition"
        open={messageOuvert}
        onOpenChange={setMessageOuvert}
      />
    </div>
  )
}
