// N94 — accès HTTP aux surcharges de traduction de la société.
//
// Séparé du provider pour rester testable (mockable) et pour que
// `I18nProvider.jsx` n'exporte que le composant (règle react-refresh).
//
// `fetchTranslationOverrides()` renvoie l'objet `{ locale: { key: value } }`
// des surcharges de la société, ou `null` en cas d'échec/absence de session —
// auquel cas le provider retombe silencieusement sur les catalogues statiques.
import api from '../api/axios'

// Endpoint léger de lecture (tout rôle). `suppressErrorToast` : un utilisateur
// non authentifié (401) ou hors ligne ne doit JAMAIS voir un toast d'erreur —
// les surcharges sont un « bonus » silencieux par-dessus le catalogue statique.
export async function fetchTranslationOverrides() {
  try {
    const r = await api.get('/parametres/traductions/effective/', {
      suppressErrorToast: true,
    })
    const ov = r?.data?.overrides
    return ov && typeof ov === 'object' ? ov : {}
  } catch {
    return null
  }
}
