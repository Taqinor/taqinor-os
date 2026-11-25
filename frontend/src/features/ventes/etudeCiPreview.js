// CIQ124 — pont entre le générateur de devis (commercial / industriel) et le
// moteur serveur C&I (CIQ118, `POST /ventes/etude-ci/preview/`). Les fonctions
// PURES vivent dans `etudeCiPreviewPur.js` (testables sous `node --test`) ; ce
// module ajoute UN hook React qui les enchaîne avec l'appel réseau
// debouncé/annulable. AUCUN calcul local : l'écran affiche la réponse.
import ventesApi from '../../api/ventesApi'
import { useApercuServeur } from './quote/hooks/useApercuServeur'
import { lignesEcranVersPayload } from './quote/lignesEcran'
import { corpsCiSurLesLignes } from './etudeCiPreviewPur'

export {
  construireCorpsCi, consommationExprimee, alertesAffichables,
  libelleProvenance, nombreOuNull, reponseAJour, corpsCiSurLesLignes, reponseAffichee,
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

/**
 * T4-X6-008 — l'aperçu de l'écran : en édition (`corps.devis`), LE calcul rangé du devis
 * sur les lignes de l'écran (les cartes décrivent ce que le devis VEND) ; l'aperçu libre
 * du moteur ne sert plus que son CONSEIL de taille (`conseil` = son bloc `taille`,
 * proposé à part, « Appliquer »). Hors édition : l'aperçu du moteur, tel quel.
 */
export function useEtudeCiEcran(corps, lignes) {
  const surLignes = corpsCiSurLesLignes(corps, lignes ? lignesEcranVersPayload(lignes) : null)
  const libre = useEtudeCiPreview(corps)
  const lu = useEtudeCiPreview(surLignes)
  if (!surLignes) return libre
  return { ...lu, conseil: libre.donnees?.taille ?? null }
}

/**
 * T4-X6-007 — ce que la carte résultat lit en plus de l'aperçu : le retour de l'offre
 * réseau SERVI par l'économie C&I sur les lignes de CETTE option (le chiffre du PDF,
 * au dixième) et le geste « Appliquer » du conseil de taille.
 */
export const apercuCiPourLesCartes = (apercuCi, apercuEcoCi, appliquerConseil) => ({
  ...apercuCi, appliquerConseil,
  retourSans: apercuEcoCi?.donnees?.indicateurs?.retour_dixieme_ans ?? null,
})
