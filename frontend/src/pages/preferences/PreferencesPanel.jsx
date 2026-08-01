// VX46 — « Mes préférences » : centre de personnalisation par utilisateur.
// La personnalisation existait déjà mais était éparpillée sans surface :
// thème (design/ThemeToggle, réutilisé tel quel), densité par défaut
// (design/theme-context useDensity, réutilisé tel quel — s'applique aux
// DataTable), module d'atterrissage au login (nouveau, ce fichier), réduction
// de mouvement, qualité photo NTMOB12 (nouveaux, prefs.js) — persistance
// localStorage uniquement (motif COLLAPSE_KEY, Layout.jsx:16), propre à CET
// APPAREIL. Exception : NTMOB6 « Accueil mobile automatique par rôle » vit
// côté serveur (mobile_home_route, /auth/me) — seul réglage de ce panneau à
// appeler un endpoint backend, documenté sur MobileHomeToggle ci-dessous.
//
// Ouvert depuis le menu utilisateur du Header (Dialog, pas une route — reste
// dans le périmètre `pages/preferences/` + `Header.jsx` de cette tâche).
import { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
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
import api from '../../api/axios'
import { fetchMe } from '../../features/auth/store/authSlice'
import {
  getLandingModule, setLandingModule, LANDING_LAST_MODULE,
  getReducedMotionPref, setReducedMotionPref,
  getPhotoQualityPref, setPhotoQualityPref,
  getAppResumePref, setAppResumePref, APP_RESUME_ALWAYS, APP_RESUME_NEVER,
  // EZ9 — mode « Plein soleil » (terrain).
  getSunlightPref, setSunlightPref,
} from './prefs'

// NTMOB6 — sélecteur de démarrage par rôle : « revenir au dashboard classique
// via le menu ». `mobile_home_route` vit CÔTÉ SERVEUR (/auth/me), pas en
// localStorage comme les autres réglages de ce panneau — c'est le même champ
// que Dashboard.jsx lit pour décider du redémarrage automatique sur mobile.
// NULL/undefined (pas encore décidé) et toute route mémorisée comptent comme
// « automatique » ; seule la chaîne vide explicite est un opt-out.
function MobileHomeToggle() {
  const dispatch = useDispatch()
  const mobileHomeRoute = useSelector((s) => s.auth.user?.mobile_home_route)
  const [busy, setBusy] = useState(false)
  const automatic = mobileHomeRoute !== ''

  const onToggle = async (checked) => {
    setBusy(true)
    try {
      // checked → automatique (repasse à « pas encore décidé », recalculé au
      // prochain atterrissage mobile) ; décoché → opt-out explicite ('').
      await api.post('/auth/mobile-home-route/', { route: checked ? null : '' })
      await dispatch(fetchMe())
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <label htmlFor="pref-mobile-home" className="text-sm font-semibold text-foreground">
          Accueil mobile automatique par rôle
        </label>
        <p className="text-xs text-muted-foreground">
          Sur téléphone, atterrir directement sur l'accueil adapté à votre rôle
          (Ma journée, Mes leads…) plutôt que sur le tableau de bord classique.
        </p>
      </div>
      <Switch
        id="pref-mobile-home"
        checked={automatic}
        disabled={busy}
        onCheckedChange={onToggle}
        aria-label="Accueil mobile automatique par rôle" />
    </div>
  )
}

const DENSITY_OPTIONS = [
  { value: 'comfortable', label: 'Confort' },
  { value: 'compact', label: 'Compact' },
]

// NTMOB12 — « Standard compressé » (défaut) recompresse chaque photo avant
// envoi (bord long 1600px, JPEG q0.75) sur les écrans de capture terrain ;
// « Original » envoie le fichier tel quel (plus de données, aucune perte).
const PHOTO_QUALITY_OPTIONS = [
  { value: 'compressed', label: 'Standard compressé' },
  { value: 'original', label: 'Original' },
]

export default function PreferencesPanel({ open, onOpenChange }) {
  const { density, setDensity } = useDensity()
  const [landing, setLanding] = useState(getLandingModule)
  const [reducedMotion, setReducedMotion] = useState(getReducedMotionPref)
  const [photoQuality, setPhotoQuality] = useState(getPhotoQualityPref)
  const [appResume, setAppResume] = useState(getAppResumePref)

  // ODY29 — que faire de la route mémorisée quand on rouvre une app.
  const handleAppResumeChange = (e) => {
    const value = e.target.value
    setAppResume(value)
    setAppResumePref(value)
  }
  // EZ9 — le réglage vit aussi en tête des deux écrans terrain ; ici c'est le
  // même état persisté, pas une seconde source.
  const [sunlight, setSunlight] = useState(getSunlightPref)

  const handleLandingChange = (e) => {
    const value = e.target.value
    setLanding(value)
    setLandingModule(value)
  }

  const handleReducedMotionChange = (checked) => {
    setReducedMotion(checked)
    setReducedMotionPref(checked)
  }

  const handleSunlightChange = (checked) => {
    setSunlight(checked)
    setSunlightPref(checked)
  }

  const handlePhotoQualityChange = (value) => {
    setPhotoQuality(value)
    setPhotoQualityPref(value)
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
              {/* ODY3 — le Menu d'accueil est le défaut du paradigme
                  (« j'ouvre → MES apps ») ; « dernier module visité » reste
                  disponible, mais en choix explicite. */}
              <option value="">Menu d'accueil — mes applications (par défaut)</option>
              <option value={LANDING_LAST_MODULE}>Dernier module visité</option>
              {landingOptions.map((c) => (
                <option key={c.key} value={c.key}>{c.nav.label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted-foreground">
              L'écran ouvert automatiquement après la connexion.
            </p>
          </div>

          {/* ODY29 — chaque app se souvient de l'endroit où vous l'avez
              quittée (le temps de la session). Ce réglage dit quoi en faire :
              le proposer, y aller tout de suite, ou l'ignorer. */}
          <div>
            <label htmlFor="pref-app-resume" className="mb-1.5 block text-sm font-semibold text-foreground">
              À l'ouverture d'une app
            </label>
            <select
              id="pref-app-resume"
              value={appResume}
              onChange={handleAppResumeChange}
              className="h-9 w-full rounded-md border border-border bg-card px-2.5 text-sm text-foreground"
            >
              <option value="">Proposer de reprendre (par défaut)</option>
              <option value={APP_RESUME_ALWAYS}>Toujours reprendre où j'en étais</option>
              <option value={APP_RESUME_NEVER}>Toujours ouvrir le cockpit de l'app</option>
            </select>
            <p className="mt-1 text-xs text-muted-foreground">
              Chaque app retient votre dernier écran pendant la session ; les
              filtres et tris des tableaux, eux, restent enregistrés comme avant.
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

          {/* EZ9 — mode terrain : contraste extrême pour la lumière directe. */}
          <div className="flex items-center justify-between gap-3">
            <div>
              <label htmlFor="pref-sunlight" className="text-sm font-semibold text-foreground">
                Mode « Plein soleil »
              </label>
              <p className="text-xs text-muted-foreground">
                Blanc pur, encre noire, bordures franches, ombres coupées — pour
                travailler écran en plein soleil. La taille du texte ne change pas.
              </p>
            </div>
            <Switch
              id="pref-sunlight"
              checked={sunlight}
              onCheckedChange={handleSunlightChange}
            />
          </div>

          <div>
            <div className="mb-1.5 text-sm font-semibold text-foreground">
              Qualité photo
            </div>
            <Segmented
              value={photoQuality}
              onChange={handlePhotoQualityChange}
              options={PHOTO_QUALITY_OPTIONS}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Sur le terrain (checklist, numérisation, SAV), « Standard compressé »
              réduit la consommation data sans perte visible ; « Original » envoie
              la photo telle quelle.
            </p>
          </div>

          <MobileHomeToggle />
        </div>
      </DialogContent>
    </Dialog>
  )
}
