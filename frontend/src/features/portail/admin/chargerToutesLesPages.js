// ADOC32 — un écran d'administration portail lit TOUTES les pages de
// l'enveloppe DRF {count, next, results}, jamais la seule page 1 (un compte
// au-delà de la page 1 restait invisible donc impossible à révoquer).
// `liste(page)` renvoie la promesse axios d'UNE page. Avec `etat`
// ({ setRows, setLoadError, setLoading }), les lignes complètes sont posées
// dans l'écran, l'échec lève le drapeau d'erreur et le chargement se termine
// dans tous les cas ; sans `etat`, la promesse rend le tableau complet.
import { fetchAllPages } from '../../../utils/fetchAllPages'

export function chargerToutesLesPages(liste, etat) {
  const lignes = fetchAllPages((page) => liste(page).then((r) => r.data))
    .then((data) => (Array.isArray(data) ? data : (data?.results ?? [])))
  if (!etat) return lignes
  return lignes
    .then(etat.setRows)
    .catch(() => etat.setLoadError(true))
    .finally(() => etat.setLoading(false))
}

export default chargerToutesLesPages
