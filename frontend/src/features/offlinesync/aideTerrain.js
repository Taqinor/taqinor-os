// NTMOB33 — logique PURE du bandeau d'onboarding contextuel TERRAIN.
// Distinct du guide global FG16 (`OnboardingCoachmarks`, tour de l'app pour
// l'administrateur) : ici, 3 phrases affichées UNE SEULE FOIS au premier accès
// à un écran terrain, puis plus jamais. Aucune donnée serveur, aucun modèle :
// un drapeau localStorage PAR UTILISATEUR (un téléphone partagé entre deux
// techniciens ne masque donc pas l'aide au second).

export const ETAPES = [
  'Voici vos interventions du jour.',
  'Appuyez pour capturer une photo.',
  'Synchronisation automatique au retour du réseau.',
]

export function cleOnboarding(userId) {
  return `taqinor.onboardingTerrain.${userId ?? 'anonyme'}`
}

function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

/** Vrai tant que CET utilisateur n'a pas fermé l'aide sur cet appareil. */
export function doitAfficherOnboarding(userId) {
  try {
    const s = storage()
    if (!s) return false
    return s.getItem(cleOnboarding(userId)) !== '1'
  } catch {
    // Stockage indisponible : on n'affiche PAS (mieux vaut rater l'aide que
    // la réafficher à chaque ouverture d'écran).
    return false
  }
}

export function marquerOnboardingVu(userId) {
  try {
    storage()?.setItem(cleOnboarding(userId), '1')
  } catch { /* stockage indisponible : rien à persister */ }
}
