// VX46 — « Mes préférences » : centre de personnalisation par utilisateur.
// La personnalisation existait déjà mais était éparpillée sans surface :
// thème (design/ThemeToggle, réutilisé tel quel), densité par défaut
// (design/theme-context useDensity, réutilisé tel quel — s'applique aux
// DataTable), module d'atterrissage au login (nouveau, ce fichier), réduction
// de mouvement (nouveau, prefs.js). AUCUN nouvel endpoint backend — persistance
// localStorage uniquement (motif COLLAPSE_KEY, Layout.jsx:16).
//
// Ouvert depuis le menu utilisateur du Header (Dialog, pas une route — reste
// dans le périmètre `pages/preferences/` + `Header.jsx` de cette tâche).
import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../ui/Dialog'
// VX185/wave-3 perf: import direct (jamais le barrel `../../ui`) — PreferencesPanel
// est chargé par Header.jsx, statique (Layout.jsx -> router/index.jsx -> main.jsx),
// donc tout ce que le barrel touche (dont datatable -> recharts/pdfjs-dist)
// finirait en `<link rel="modulepreload">` sur chaque page.
import { Segmented } from '../../ui/Segmented'
import { Switch } from '../../ui/Switch'
import { ThemeToggle } from '../../design/ThemeToggle'
import { useDensity } from '../../design/theme-context'
import { moduleConfigs } from '../../router/moduleRoutes'
import {
  getLandingModule, setLandingModule,
  getReducedMotionPref, setReducedMotionPref,
} from './prefs'

const DENSITY_OPTIONS = [
  { value: 'comfortable', label: 'Confort' },
  { value: 'compact', label: 'Compact' },
]

export default function PreferencesPanel({ open, onOpenChange }) {
  const { density, setDensity } = useDensity()
  const [landing, setLanding] = useState(getLandingModule)
  const [reducedMotion, setReducedMotion] = useState(getReducedMotionPref)

  const handleLandingChange = (e) => {
    const value = e.target.value
    setLanding(value)
    setLandingModule(value)
  }

  const handleReducedMotionChange = (checked) => {
    setReducedMotion(checked)
    setReducedMotionPref(checked)
  }

  // Modules « coquille » avec cockpit (nav.items[0].to) — mêmes candidats que
  // le lanceur d'apps (VX9) et les épingles (VX10).
  const landingOptions = moduleConfigs.filter((c) => c.nav?.items?.[0]?.to)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="Mes préférences">
        <DialogHeader>
          <DialogTitle>Mes préférences</DialogTitle>
          <DialogDescription>
            Personnalisez votre espace. Chaque réglage est propre à votre compte
            et persiste sur cet appareil.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5">
          <div>
            <div className="mb-1.5 text-sm font-semibold text-foreground">Thème</div>
            <ThemeToggle />
          </div>

          <div>
            <div className="mb-1.5 text-sm font-semibold text-foreground">
              Densité par défaut
            </div>
            <Segmented value={density} onChange={setDensity} options={DENSITY_OPTIONS} />
            <p className="mt-1 text-xs text-muted-foreground">
              S'applique aux tableaux (lignes plus ou moins compactes).
            </p>
          </div>

          <div>
            <label htmlFor="pref-landing" className="mb-1.5 block text-sm font-semibold text-foreground">
              Module d'atterrissage au login
            </label>
            <select
              id="pref-landing"
              value={landing}
              onChange={handleLandingChange}
              className="h-9 w-full rounded-md border border-border bg-card px-2.5 text-sm text-foreground"
            >
              <option value="">Dernier module visité (par défaut)</option>
              {landingOptions.map((c) => (
                <option key={c.key} value={c.key}>{c.nav.label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted-foreground">
              L'écran ouvert automatiquement après la connexion.
            </p>
          </div>

          <div className="flex items-center justify-between gap-3">
            <div>
              <label htmlFor="pref-reduced-motion" className="text-sm font-semibold text-foreground">
                Réduire les animations
              </label>
              <p className="text-xs text-muted-foreground">
                Coupe les transitions/animations de mouvement, même si votre système ne le demande pas.
              </p>
            </div>
            <Switch
              id="pref-reduced-motion"
              checked={reducedMotion}
              onCheckedChange={handleReducedMotionChange}
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
