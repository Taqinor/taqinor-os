// FG16 — Aides pour l'onboarding in-app : drapeau localStorage « déjà vu » du
// guide (coachmarks) et dérivation de l'état FAIT/À FAIRE de la checklist de
// configuration à partir des données existantes (profil entreprise, produits,
// utilisateurs). Aucun nouveau modèle serveur : on lit les endpoints déjà en
// place. Tout est défensif — un stockage indisponible (mode privé) ne casse
// jamais le rendu, et une lecture API en échec dégrade en « à faire ».
import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import stockApi from '../../api/stockApi'
import api from '../../api/axios'

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

// ── VX36 — Étapes de prise en main PARTAGÉES (hook) + rejet par société ────────
// Le hook `useOnboardingSteps()` centralise la dérivation des 3 étapes (profil
// entreprise / premier produit / premier coéquipier) pour que la bannière du
// Dashboard ET l'onglet « Prise en main » parlent d'une seule source. Aucun
// nouvel endpoint serveur : mêmes lectures que la section historique.

// Construit les 3 étapes à partir des comptes/profil déjà connus. PURE (testable
// sans React) : les composants passent profile + les comptes bruts.
export function buildOnboardingSteps({ profile, produitCount, userCount }) {
  return [
    {
      key: 'profil',
      done: isCompanyProfileComplete(profile),
      title: "Complétez le profil de l'entreprise",
      desc: "Nom, adresse et contact — utilisés en en-tête de vos devis et factures.",
      to: '/parametres',
      cta: 'Ouvrir Société & identité',
    },
    {
      key: 'produit',
      done: (produitCount ?? 0) > 0,
      title: 'Créez votre premier produit',
      desc: 'Ajoutez au catalogue un panneau, un onduleur ou un article de pompage.',
      to: '/stock',
      cta: 'Ouvrir le catalogue',
    },
    {
      // « Premier utilisateur invité » = au moins un compte au-delà du vôtre.
      key: 'equipe',
      done: (userCount ?? 0) > 1,
      title: 'Invitez un membre de votre équipe',
      desc: "Créez un compte collaborateur et attribuez-lui un rôle.",
      to: '/admin/users',
      cta: "Gérer l'équipe",
    },
  ]
}

// Clé de rejet PAR SOCIÉTÉ : masquer la bannière ne doit pas fuiter entre
// sociétés (multi-tenant). Repli sur une clé générique si l'id est absent.
function dismissKey(companyId) {
  return `taqinor.onboarding.banner.dismissed.${companyId ?? 'default'}`
}

export function isOnboardingDismissed(companyId) {
  try {
    return window.localStorage.getItem(dismissKey(companyId)) === '1'
  } catch {
    return false
  }
}

export function dismissOnboarding(companyId) {
  try {
    window.localStorage.setItem(dismissKey(companyId), '1')
  } catch { /* stockage indisponible : sans effet */ }
}

// Hook partagé : charge les comptes produits/utilisateurs (mêmes lectures que
// l'onglet « Prise en main ») et renvoie les étapes dérivées + agrégats. Le
// profil entreprise vient du store (déjà chargé par la coquille/Paramètres).
// Défensif : une lecture en échec laisse l'étape « à faire », jamais d'erreur.
export function useOnboardingSteps() {
  const profile = useSelector((s) => s.parametres?.profile)
  const [produitCount, setProduitCount] = useState(null)
  const [userCount, setUserCount] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    Promise.allSettled([
      stockApi.getProduits({ page_size: 1 }),
      api.get('/users/'),
    ]).then(([prod, users]) => {
      if (!alive) return
      setProduitCount(prod.status === 'fulfilled'
        ? countFromListResponse(prod.value.data) : null)
      setUserCount(users.status === 'fulfilled'
        ? countFromListResponse(users.value.data) : null)
    }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const steps = buildOnboardingSteps({ profile, produitCount, userCount })
  const doneCount = steps.filter((s) => s.done).length
  const allDone = doneCount === steps.length
  return { steps, doneCount, total: steps.length, allDone, loading }
}
