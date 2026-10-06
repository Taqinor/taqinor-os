// CIQ124 — pont entre le générateur de devis (commercial / industriel) et le
// moteur serveur C&I (CIQ118, `POST /ventes/etude-ci/preview/`). Les fonctions
// PURES vivent dans `etudeCiPreviewPur.js` (testables sous `node --test`) ; ce
// module ajoute UN hook React qui les enchaîne avec l'appel réseau
// debouncé/annulable. AUCUN calcul local : l'écran affiche la réponse.
import ventesApi from '../../api/ventesApi'
import { useApercuServeur } from './quote/hooks/useApercuServeur'

export {
  construireCorpsCi, consommationExprimee, alertesAffichables,
  libelleProvenance, nombreOuNull, reponseAJour,
} from './etudeCiPreviewPur'

/**
 * Hook React : appelle l'aperçu C&I, débondi ~500 ms, annulable en vol, jamais
 * périmé (hook partagé `useApercuServeur`, CIQ223). `corps` vient de
 * `construireCorpsCi` ; `null` = rien à demander (aucun appel réseau).
 * `corpsServi` nomme la saisie qui a produit `donnees` (voir `reponseAJour`).
 */
const appeler = (body, config) => (typeof ventesApi.etudeCiPreview === 'function'
  ? ventesApi.etudeCiPreview(body, config) : null)

export function useEtudeCiPreview(corps) {
  return useApercuServeur(corps, {
    appeler, erreurParDefaut: 'Aperçu du moteur C&I indisponible pour le moment.',
  })
}
