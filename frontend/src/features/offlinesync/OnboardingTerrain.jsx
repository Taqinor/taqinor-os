// NTMOB33 — bandeau d'aide contextuel, première utilisation terrain.
// Trois étapes, fermable, JAMAIS réaffiché après fermeture (drapeau
// localStorage par utilisateur). Purement UI : aucune donnée serveur nouvelle.
// Distinct du guide global FG16 (`OnboardingCoachmarks`) : celui-ci parle de la
// configuration de l'app, celui-là du geste terrain du jour.
// NOTE : le module de logique s'appelle `aideTerrain.js` et non
// `onboardingTerrain.js` — sur un FS insensible à la casse (Windows),
// `./OnboardingTerrain` résoudrait vers le `.js` avant le `.jsx`.
import { useState } from 'react'
import { X, ArrowRight } from 'lucide-react'
import {
  ETAPES, doitAfficherOnboarding, marquerOnboardingVu,
} from './aideTerrain'

/**
 * @param {number|undefined} userId — identifiant de l'utilisateur courant. Le
 *   drapeau « déjà vu » est posé PAR UTILISATEUR (un téléphone partagé entre
 *   deux techniciens ne masque pas l'aide au second). Volontairement une PROP
 *   et non un `useSelector` : ce composant se monte sur des écrans qui ne sont
 *   pas tous branchés au store, et une aide contextuelle ne doit jamais
 *   imposer une dépendance Redux à son hôte.
 */
export default function OnboardingTerrain({ userId }) {
  const [etape, setEtape] = useState(0)
  const [visible, setVisible] = useState(() => doitAfficherOnboarding(userId))

  if (!visible) return null

  const fermer = () => {
    marquerOnboardingVu(userId)
    setVisible(false)
  }

  const suivant = () => {
    if (etape >= ETAPES.length - 1) fermer()
    else setEtape(etape + 1)
  }

  return (
    <div
      role="status"
      data-testid="onboarding-terrain"
      className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm"
    >
      <span className="min-w-0 flex-1">{ETAPES[etape]}</span>
      <span className="text-xs text-muted-foreground">
        {etape + 1}/{ETAPES.length}
      </span>
      <button
        type="button"
        onClick={suivant}
        aria-label={etape >= ETAPES.length - 1 ? 'Terminer l\'aide' : 'Étape suivante'}
        className="rounded p-1 text-muted-foreground"
      >
        <ArrowRight className="size-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={fermer}
        aria-label="Fermer l'aide"
        className="rounded p-1 text-muted-foreground"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </div>
  )
}
