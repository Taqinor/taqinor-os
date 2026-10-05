// CJ2b — pont entre le générateur de devis (résidentiel) et l'endpoint moteur
// horaire (CJ2a, `POST /ventes/etude-horaire/preview/`). Fonctions PURES
// (construireCorpsPreview / etiquetteSource / lignesAffichables — testables
// sous `node --test`, voir etudeHorairePreview.test.mjs) + UN hook React qui
// les enchaîne avec l'appel réseau debouncé/annulable.
//
// RÈGLES D'HONNÊTETÉ (fondateur, absolues — voir CLAUDE.md rule #4 / DC9) :
//   1. Quand `batterie_disponible` est faux, AUCUN chiffre « avec batterie »
//      n'est affiché — jamais un 0, jamais un tiret qui se ferait passer pour
//      une mesure. `lignesAffichables` les efface elle-même en défense de
//      profondeur, même si le serveur les avait déjà mis à `null`.
//   2. Tout chiffre dérivé d'une consommation ESTIMÉE (une seule ou deux
//      factures répétées sur 12 mois) porte l'étiquette « estimation » —
//      `etiquetteSource` le décide depuis `etude.source_consommation`.
//   3. `avertissements` du serveur sont montrés tels quels (jamais réécrits).
//   4. Une donnée manquante est OMISE avec une explication FR courte, jamais
//      comblée par une valeur inventée.
import { useApercuServeur } from '../../lib/useApercuServeur'
import ventesApi from '../../api/ventesApi'
// CJ2b — les fonctions PURES vivent à côté, sans aucun import, pour rester
// exécutables sous `node --test` (voir l'en-tête de ce module-là).
export {
  construireCorpsPreview, etiquetteSource, lignesAffichables,
  verdictBatteriePourTaille,
  libelleTranche, falaiseAffichable, glitchAnnuel, balayageStockageAffichable,
  estimationConsoAffichable, LIBELLES_MOIS,
} from './etudeHorairePreviewPur'

const MESSAGE_ERREUR = "Aperçu du moteur horaire indisponible pour le moment."

// Dégradation silencieuse : méthode absente (mock de test partiel, build
// en cours de déploiement) — jamais un crash de l'écran générateur.
const appelerPreviewHoraire = (body, config) => (
  typeof ventesApi.postEtudeHorairePreview === 'function'
    ? ventesApi.postEtudeHorairePreview(body, config) : null
)

/**
 * Hook React : appelle l'aperçu moteur horaire, débondi ~500 ms, annulable en
 * vol (même patron que LeadDevisPanel.jsx — race token `cancelled` +
 * AbortController). `corps` vient de `construireCorpsPreview` ; `null` =
 * rien à demander (aucun appel réseau, `donnees` reste `null`). Ne lève
 * JAMAIS et ne laisse jamais un résultat PÉRIMÉ à l'écran : `donnees` est
 * effacé au tout début de chaque nouvel appel, avant la réponse.
 */
export function useEtudeHorairePreview(corps) {
  return useApercuServeur(corps, appelerPreviewHoraire, MESSAGE_ERREUR)
}
