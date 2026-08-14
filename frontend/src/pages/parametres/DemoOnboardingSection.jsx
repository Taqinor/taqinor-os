// NTDMO27 — onglet Paramètres « Démo & Onboarding » : regroupe les toggles du
// groupe NTDMO déjà construits séparément (mode présentation NTDMO10, reset
// démo NTDMO7, « Revoir les visites guidées » par tour NTDMO16 — réutilisés
// tels quels ici, aucune logique dupliquée) + le nouveau toggle global
// « Activer les tours contextuels pour les nouveaux utilisateurs »
// (`Company.tours_actifs`, additif, défaut True).
import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Compass } from 'lucide-react'
import demoApi from '../../api/demoApi'
import { fetchMe } from '../../features/auth/store/authSlice'
import { Card, CardContent } from '../../ui'
import { toast } from '../../ui/confirm'
import { SectionTitle } from './peComponents'
import PresentationModeToggle from './PresentationModeToggle'
import DemoResetButton from './DemoResetButton'
import { VisitesGuideesBlock } from './OnboardingSection'

// NTDMO27 — toggle global, visible pour TOUTE société (contrairement à
// PresentationModeToggle/DemoResetButton ci-dessous, réservés aux sociétés
// démo — leur propre garde interne les masque déjà, rien à ajouter ici).
function ToursActifsToggle() {
  const user = useSelector((s) => s.auth.user)
  const dispatch = useDispatch()
  const [busy, setBusy] = useState(false)

  // Défaut serveur True : absent (bootstrap) => actif, jamais un flash « off ».
  const actif = user?.company_tours_actifs !== false

  const onToggle = async () => {
    setBusy(true)
    try {
      await demoApi.setToursActifs(user.company_id, !actif)
      await dispatch(fetchMe())
      toast.success(actif ? 'Visites guidées désactivées.' : 'Visites guidées activées.')
    } catch {
      toast.error('Impossible de changer ce réglage.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card data-testid="tours-actifs-card">
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Visites guidées"
          icon={<><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>}
        />
        <p className="mb-3 text-[12px] text-muted-foreground">
          Active ou désactive l'apparition automatique des visites guidées
          (spotlight sur les écrans clés) pour les nouveaux utilisateurs de
          votre société.
        </p>
        <label className="flex cursor-pointer items-center gap-2 text-[13px] font-medium">
          <input
            type="checkbox"
            checked={actif}
            disabled={busy}
            onChange={onToggle}
            aria-label="Activer les tours contextuels pour les nouveaux utilisateurs"
          />
          <Compass className="size-4" aria-hidden="true" />
          {actif ? 'Activées' : 'Désactivées'}
        </label>
      </CardContent>
    </Card>
  )
}

export default function DemoOnboardingSection() {
  return (
    <div className="flex flex-col gap-4">
      <PresentationModeToggle />
      <DemoResetButton />
      <ToursActifsToggle />
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle
            label="Visites guidées par écran"
            icon={<><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></>}
          />
          <p className="mb-2 text-[12px] text-muted-foreground">
            Statut vu/non-vu des 6 tours par écran money-path, avec un bouton
            « Revoir » pour cet utilisateur.
          </p>
          <VisitesGuideesBlock />
        </CardContent>
      </Card>
    </div>
  )
}
