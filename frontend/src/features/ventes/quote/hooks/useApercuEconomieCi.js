// CIQ223 — aperçu SERVEUR de l'économie C&I (`POST /ventes/economie-ci/preview/`,
// contrat `economie_ci.json`). Débondi (~500 ms), annulable en vol, jamais
// périmé (hook partagé `useApercuServeur`). `corps` = {sortie_etude_ci, saisies,
// lignes} ou `null` (aucun appel). AUCUN calcul ici : l'écran affiche la réponse.
import ventesApi from '../../../../api/ventesApi'
import { htFromTtc } from '../../solar.js'
import { deuxOptionsDeclarees, lignesDeLOption } from '../../calc/totaux.js'
import { useApercuServeur } from './useApercuServeur'

const appeler = (body, config) => (typeof ventesApi.economieCiPreview === 'function'
  ? ventesApi.economieCiPreview(body, config) : null)

export function useApercuEconomieCi(corps, { delai = 500 } = {}) {
  return useApercuServeur(corps, {
    appeler, delai, erreurParDefaut: "Aperçu de l'économie C&I indisponible pour le moment.",
  })
}

/**
 * T4-X6-007 — les lignes que l'économie C&I chiffre : celles de l'option SANS batterie
 * seulement quand le devis déclare deux options (`lignesDeLOption`, miroir de
 * `utils/options.filter_lines_for_option` que lit le PDF), sinon toutes. Avant, les
 * lignes des DEUX options entraient dans l'investissement de l'offre réseau.
 */
export function lignesEconomieCi(lignes, { scenario, produits } = {}) {
  const option = deuxOptionsDeclarees(lignes, { scenario, produits })
    ? lignesDeLOption(lignes, 'sans', { scenario, produits }) : (lignes || [])
  return option.map((l) => {
    const q = parseFloat(l.quantite) || 0
    const tva = parseFloat(l.taux_tva ?? 20)
    const ttc = (parseFloat(l.prix_unit_ttc) || 0) * q
    return {
      produit: Number(l.produit), quantite: q, taux_tva: tva,
      totaux: { ht: htFromTtc(parseFloat(l.prix_unit_ttc) || 0, tva) * q, ttc },
    }
  })
}
