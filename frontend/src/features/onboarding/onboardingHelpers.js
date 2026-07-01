// FG16 — Aides pour l'onboarding in-app : drapeau localStorage « déjà vu » du
// guide (coachmarks) et dérivation de l'état FAIT/À FAIRE de la checklist de
// configuration à partir des données existantes (profil entreprise, produits,
// utilisateurs). Aucun nouveau modèle serveur : on lit les endpoints déjà en
// place. Tout est défensif — un stockage indisponible (mode privé) ne casse
// jamais le rendu, et une lecture API en échec dégrade en « à faire ».

// Version du guide : incrémenter pour re-déclencher le guide chez tout le monde
// après une refonte des étapes.
export const COACHMARK_VERSION = 1
const SEEN_KEY = 'taqinor.onboarding.coachmarks.seen'
// Événement custom (window) pour re-déclencher le guide depuis les Paramètres
// sans coupler les composants entre eux.
export const REPLAY_EVENT = 'taqinor:onboarding:replay'

// ── Drapeau « déjà vu » (localStorage, tolérant aux erreurs) ────────────────
export function hasSeenCoachmarks() {
  try {
    return window.localStorage.getItem(SEEN_KEY) === String(COACHMARK_VERSION)
  } catch {
    // Stockage indisponible : on considère « déjà vu » pour ne PAS harceler
    // l'utilisateur d'un guide qu'on ne saurait de toute façon pas mémoriser.
    return true
  }
}

// Sous automatisation navigateur (Playwright / CI e2e), ne PAS ouvrir le guide
// automatiquement : son fond plein écran intercepterait les clics des tests, et
// une ouverture auto n'a de sens que pour un humain. Le rejeu manuel depuis les
// Paramètres reste toujours possible.
function isAutomatedBrowser() {
  try {
    return typeof navigator !== 'undefined' && navigator.webdriver === true
  } catch {
    return false
  }
}

// Faut-il ouvrir le guide automatiquement au montage ? Seulement si jamais vu
// ET hors automatisation navigateur.
export function shouldAutoOpenCoachmarks() {
  return !hasSeenCoachmarks() && !isAutomatedBrowser()
}

export function markCoachmarksSeen() {
  try {
    window.localStorage.setItem(SEEN_KEY, String(COACHMARK_VERSION))
  } catch { /* stockage indisponible : on ignore silencieusement */ }
}

export function resetCoachmarks() {
  try {
    window.localStorage.removeItem(SEEN_KEY)
  } catch { /* idem */ }
}

// Re-déclenche le guide (utilisé par le bouton « Revoir le guide » des
// Paramètres) : on efface le drapeau puis on émet l'événement de rejeu.
export function replayCoachmarks() {
  resetCoachmarks()
  try {
    window.dispatchEvent(new CustomEvent(REPLAY_EVENT))
  } catch { /* environnement sans window : sans effet */ }
}

// ── État de la checklist de configuration ───────────────────────────────────
// « Profil entreprise renseigné » = les champs d'en-tête indispensables aux PDF
// (nom + adresse + au moins un moyen de contact) sont remplis.
export function isCompanyProfileComplete(profile) {
  if (!profile) return false
  const filled = (v) => typeof v === 'string' && v.trim().length > 0
  return filled(profile.nom)
    && filled(profile.adresse)
    && (filled(profile.email) || filled(profile.telephone))
}

// Compte robuste d'une réponse liste DRF (paginée { count, results } ou brute).
export function countFromListResponse(data) {
  if (!data) return 0
  if (typeof data.count === 'number') return data.count
  const arr = data.results ?? data
  return Array.isArray(arr) ? arr.length : 0
}
