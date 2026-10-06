// CIQ223 — aperçu SERVEUR de l'économie C&I (`POST /ventes/economie-ci/preview/`,
// contrat `economie_ci.json`). Débondi (~500 ms), annulable en vol, jamais
// périmé (hook partagé `useApercuServeur`). `corps` = {sortie_etude_ci, saisies,
// lignes} ou `null` (aucun appel). AUCUN calcul ici : l'écran affiche la réponse.
import ventesApi from '../../../../api/ventesApi'
import { useApercuServeur } from './useApercuServeur'

const appeler = (body, config) => (typeof ventesApi.economieCiPreview === 'function'
  ? ventesApi.economieCiPreview(body, config) : null)

export function useApercuEconomieCi(corps, { delai = 500 } = {}) {
  return useApercuServeur(corps, {
    appeler, delai, erreurParDefaut: "Aperçu de l'économie C&I indisponible pour le moment.",
  })
}
