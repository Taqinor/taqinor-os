import { useState } from 'react'
import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import { Rocket, ArrowRight, X } from 'lucide-react'
import { Card, Button, Progress } from '../ui'
import {
  useOnboardingSteps, isOnboardingDismissed, dismissOnboarding,
} from '../features/onboarding/onboardingHelpers'

/* VX36 — L'onboarding sort de sa cachette : bannière de prise en main en haut
   du Dashboard, visible AU PREMIER LOGIN (la checklist « Prise en main » était
   enterrée dans l'onglet 1 de 24 des Paramètres). Se masque d'elle-même quand :
   toutes les étapes sont faites, l'utilisateur a cliqué « Ne plus afficher »
   (persisté PAR SOCIÉTÉ), ou pendant le chargement initial de l'état.
   « Créer un artefact réel dans la première minute. » */
export default function OnboardingBanner() {
  const companyId = useSelector((s) => s.auth.user?.active_company_id)
  const { steps, doneCount, total, allDone, loading } = useOnboardingSteps()
  // État de rejet en state local (déclenche un re-render au clic « Ne plus
  // afficher ») initialisé depuis le localStorage scoped société.
  const [dismissed, setDismissed] = useState(() => isOnboardingDismissed(companyId))

  // Rien à montrer : chargement, configuration terminée, ou rejetée.
  if (loading || allDone || dismissed) return null

  const pct = Math.round((doneCount / total) * 100)
  const nextStep = steps.find((s) => !s.done)

  const onDismiss = () => {
    dismissOnboarding(companyId)
    setDismissed(true)
  }

  return (
    <Card className="mb-4 p-4 sm:p-5" data-testid="onboarding-banner">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary">
            <Rocket className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">Prise en main</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {doneCount} / {total} étapes complétées — encore quelques réglages pour bien démarrer.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Ne plus afficher la prise en main"
          title="Ne plus afficher"
        >
          <X className="size-3.5" aria-hidden="true" /> Ne plus afficher
        </button>
      </div>

      <div className="mt-3">
        <Progress value={pct} tone="primary" />
      </div>

      {nextStep && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <span className="min-w-0 truncate text-sm text-foreground">
            <span className="font-medium">Prochaine étape :</span> {nextStep.title}
          </span>
          <Button asChild size="sm" className="shrink-0">
            <Link to={nextStep.to}>
              {nextStep.cta} <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      )}
    </Card>
  )
}
