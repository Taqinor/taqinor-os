import { Lightbulb } from 'lucide-react'
import { Card, CardContent } from '../../ui'
import ProposerIdeeForm from './ProposerIdeeForm'

/* ============================================================================
   NTIDE8 — Page « proposer une idée » (route dédiée /innovation/proposer).
   Immédiate (pas de brouillon) : le submit crée l'Idee et redirige vers son
   détail avec un toast de confirmation (voir ProposerIdeeForm).
   ========================================================================== */

export default function ProposerIdeePage() {
  return (
    <div className="page mx-auto flex max-w-xl flex-col gap-6">
      <h1 className="inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight">
        <Lightbulb className="size-5" aria-hidden="true" />
        Proposer une idée
      </h1>
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <ProposerIdeeForm />
        </CardContent>
      </Card>
    </div>
  )
}
