import { useCallback, useRef, useState } from 'react'

// VX243(c) — garde d'édition périmée (stale-write), générique
// (Lead/Devis/Facture — tout enregistrement exposant `updated_at`).
//
// Le verrou optimiste COMPLET (409 bloquant au save) reste territoire YDATA ;
// ce hook est la mitigation 80/20 : au SUBMIT, un GET léger relit
// `updated_at` côté serveur et le compare à la valeur capturée à
// l'OUVERTURE de la fiche (`openedAt`). Si elle a changé — quelqu'un d'autre
// a sauvegardé entre-temps (2 onglets, 2 collègues) — on affiche une
// bannière NON BLOQUANTE avec un choix explicite : « Revoir » (annule CE
// submit, laisse l'utilisateur rafraîchir/comparer) ou « Enregistrer quand
// même » (force la sauvegarde en cours), plutôt que d'écraser silencieusement
// le travail d'un collègue sans le signaler.
//
// Sans `openedAt` (création, pas édition) ou sans `fetchLatest`, le hook ne
// fait AUCUNE requête — comportement historique inchangé.
//
// `timestampField` = nom du champ d'horodatage de fraîcheur sur l'objet
// (`updated_at` pour Devis/Facture ; `date_modification` pour Lead) — c'est
// LUI qu'on compare entre l'ouverture et le re-GET.
export function useStaleGuard({
  openedAt, fetchLatest, timestampField = 'updated_at',
} = {}) {
  // { by, at } | null — auteur/horodatage de la modification concurrente
  // détectée au dernier `checkBeforeSave()`.
  const [staleInfo, setStaleInfo] = useState(null)
  const forcedRef = useRef(false)

  const dismiss = useCallback(() => {
    setStaleInfo(null)
  }, [])

  // À appeler AVANT la mutation d'écriture. Renvoie `true` si le submit peut
  // continuer (rien de périmé détecté, ou l'utilisateur a déjà choisi
  // « enregistrer quand même » pour CE submit), `false` s'il faut
  // interrompre le submit — la bannière reste affichée pour décision.
  const checkBeforeSave = useCallback(async () => {
    if (!openedAt || typeof fetchLatest !== 'function') return true
    if (forcedRef.current) {
      forcedRef.current = false // un seul forçage vaut pour CE submit
      return true
    }
    try {
      const latest = await fetchLatest()
      const latestAt = latest?.[timestampField]
      if (latestAt && latestAt !== openedAt) {
        setStaleInfo({
          by: latest?.updated_by_nom || latest?.archived_by_nom || null,
          at: latestAt,
        })
        return false
      }
      return true
    } catch {
      // Best-effort : une vérification en échec (réseau, endpoint
      // indisponible) ne doit JAMAIS bloquer un enregistrement légitime.
      return true
    }
  }, [openedAt, fetchLatest, timestampField])

  // « Enregistrer quand même » — arme un forçage à usage unique et efface
  // la bannière ; l'appelant doit ensuite RE-SOUMETTRE (le hook n'invoque
  // jamais lui-même la mutation, il ne fait que garder le submit).
  const force = useCallback(() => {
    forcedRef.current = true
    setStaleInfo(null)
  }, [])

  return { staleInfo, checkBeforeSave, dismiss, force }
}

export default useStaleGuard
