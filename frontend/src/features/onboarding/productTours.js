// NTDMO14/15 — aides pour les visites guidées (« product tours ») par écran.
// Distinct du guide d'accueil global (FG16 OnboardingCoachmarks, localStorage,
// une seule séquence) : ici CHAQUE écran money-path a son propre tour, tracké
// côté serveur (company + user, `apps/onboarding` NTDMO14) pour ne jamais le
// remontrer une fois vu — même après déconnexion/reconnexion ou changement de
// poste. Tout est défensif : une lecture API en échec dégrade en « aucun
// tour » (jamais d'erreur visible).
import api from '../../api/axios'

// NTDMO15 — un tour ne se déclenche automatiquement que pour un nouvel
// utilisateur (< 30 jours depuis `date_joined`). `date_joined` absent (donnée
// non chargée) => on NE montre PAS le tour automatiquement plutôt que de
// risquer de harceler un utilisateur ancien.
const NEW_USER_WINDOW_DAYS = 30

export function isNewUser(user, now = new Date()) {
  const raw = user?.date_joined
  if (!raw) return false
  const joined = new Date(raw)
  if (Number.isNaN(joined.getTime())) return false
  const ageDays = (now.getTime() - joined.getTime()) / (1000 * 60 * 60 * 24)
  return ageDays >= 0 && ageDays < NEW_USER_WINDOW_DAYS
}

// Trouve le tour dont `ecran_cible` correspond au chemin courant (correspondance
// exacte — les 6 tours ciblent des routes précises, pas des sous-arbres).
export function findTourForPath(tours, pathname) {
  if (!Array.isArray(tours)) return null
  return tours.find((t) => t.ecran_cible === pathname) ?? null
}

// Un seul appel réseau, mis en cache en mémoire pour la session (NTDMO14 —
// catalogue chargé sans requête bloquante répétée à chaque changement de page).
let cachedToursPromise = null

export function fetchTours({ force = false } = {}) {
  if (force || !cachedToursPromise) {
    cachedToursPromise = api.get('/onboarding/tours/')
      .then((r) => (Array.isArray(r.data) ? r.data : []))
      .catch(() => [])
  }
  return cachedToursPromise
}

// Invalide le cache mémoire (utilisé après « vu »/« revoir » pour refléter le
// nouvel état sans attendre un rechargement de page).
export function invalidateToursCache() {
  cachedToursPromise = null
}

export function markTourSeen(tourKey) {
  return api.post(`/onboarding/tours/${tourKey}/vu/`)
    .then((r) => { invalidateToursCache(); return r.data })
    .catch(() => null)
}

// NTDMO16 — bouton « Revoir » (Paramètres) : remet le tour à zéro.
export function reviewTour(tourKey) {
  return api.post(`/onboarding/tours/${tourKey}/revoir/`)
    .then((r) => { invalidateToursCache(); return r.data })
    .catch(() => null)
}
