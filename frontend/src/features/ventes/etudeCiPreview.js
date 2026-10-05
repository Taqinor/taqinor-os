// CIQ124 — pont entre le générateur de devis (commercial / industriel) et le
// moteur serveur C&I (CIQ118, `POST /ventes/etude-ci/preview/`). Les fonctions
// PURES vivent dans `etudeCiPreviewPur.js` (testables sous `node --test`) ; ce
// module ajoute UN hook React qui les enchaîne avec l'appel réseau
// debouncé/annulable. AUCUN calcul local : l'écran affiche la réponse.
import { useEffect, useState } from 'react'
import { useDebouncedValue } from '../../lib/debounce'
import ventesApi from '../../api/ventesApi'

export {
  construireCorpsCi, consommationExprimee, alertesAffichables,
  libelleProvenance, nombreOuNull, reponseAJour,
} from './etudeCiPreviewPur'

/**
 * Hook React : appelle l'aperçu C&I, débondi ~500 ms, annulable en vol
 * (AbortController + jeton `cancelled`, patron `useEtudeHorairePreview`).
 * `corps` vient de `construireCorpsCi` ; `null` = rien à demander (aucun
 * appel réseau). Le résultat est EFFACÉ au début de chaque appel : jamais un
 * chiffre périmé à l'écran. `corpsServi` nomme la saisie qui a produit
 * `donnees` (voir `reponseAJour`).
 */
export function useEtudeCiPreview(corps) {
  const corpsKey = corps ? JSON.stringify(corps) : null
  const debouncedKey = useDebouncedValue(corpsKey, 500)
  const [donnees, setDonnees] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [corpsServi, setCorpsServi] = useState(null)

  useEffect(() => {
    if (!debouncedKey) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète l'absence de corps
      setDonnees(null)
      setCorpsServi(null)
      setChargement(false)
      setErreur(null)
      return undefined
    }
    if (typeof ventesApi.etudeCiPreview !== 'function') return undefined
    let body
    try { body = JSON.parse(debouncedKey) } catch { body = null }
    if (!body) return undefined

    let cancelled = false
    const controller = new AbortController()
    setChargement(true)
    setErreur(null)
    setDonnees(null)
    setCorpsServi(null)
    ventesApi.etudeCiPreview(body, { signal: controller.signal })
      .then((res) => {
        if (cancelled) return
        setDonnees(res.data)
        setCorpsServi(debouncedKey)
      })
      .catch((err) => {
        if (cancelled) return
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        setErreur('Aperçu du moteur C&I indisponible pour le moment.')
      })
      .finally(() => { if (!cancelled) setChargement(false) })
    return () => { cancelled = true; controller.abort() }
  }, [debouncedKey])

  return { donnees, chargement, erreur, corpsServi, corpsKey }
}
