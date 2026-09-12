// NTI18N3 — accès HTTP à la langue d'interface persistée serveur
// (`CustomUser.langue_interface`, PATCH /auth/me/langue/).
//
// Séparé du provider (même raison que `overridesApi.js`, N94) : reste
// testable/mockable et n'affecte pas la règle react-refresh d'`I18nProvider`.
import api from '../api/axios'

// Best-effort, silencieux : la persistance serveur est un « bonus » de
// confort multi-poste — un échec (hors ligne, session expirée) ne doit
// jamais bloquer ni faire échouer la bascule de langue LOCALE, déjà
// appliquée par `I18nProvider` avant cet appel.
export async function patchLangueInterface(locale) {
  try {
    await api.patch('/auth/me/langue/', { langue_interface: locale },
      { suppressErrorToast: true })
    return true
  } catch {
    return false
  }
}
