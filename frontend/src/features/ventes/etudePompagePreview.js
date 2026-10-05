// AGR127 — pont entre le générateur (marché agricole) et l'aperçu SERVEUR du
// pompage (AGR121, `POST /ventes/etude-pompage/preview/`). Les fonctions
// PURES vivent dans `etudePompagePreviewPur.js` (testables sous `node
// --test`) ; ce module ajoute UN hook React debouncé (~500 ms), annulable en
// vol, qui EFFACE le résultat au début de chaque appel (jamais un résultat
// périmé à l'écran). Aucun calcul local : D-AGR-1, un seul calcul serveur.
import { useEffect, useState } from 'react'
import { useDebouncedValue } from '../../lib/debounce'
import api from '../../api/axios'

export {
  construireCorpsPompage, manquantsPompage, besoinExprime, hauteurConnue,
  alertesAffichables, libelleProvenance, nombreOuNull,
} from './etudePompagePreviewPur'

/** L'appel HTTP (exporté pour les tests composant qui le simulent). */
export const postEtudePompagePreview = (body, config = {}) =>
  api.post('/ventes/etude-pompage/preview/', body, config)

/**
 * `corps` vient de `construireCorpsPompage` ; `null` = rien à demander (aucun
 * appel, `donnees` reste `null`). Ne lève jamais.
 */
export function useEtudePompagePreview(corps) {
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
    let body
    try { body = JSON.parse(debouncedKey) } catch { body = null }
    if (!body) return undefined

    let cancelled = false
    const controller = new AbortController()
    // Jamais de résultat périmé pendant le recalcul : on efface avant l'appel.
    setChargement(true)
    setErreur(null)
    setDonnees(null)
    setCorpsServi(null)
    postEtudePompagePreview(body, { signal: controller.signal })
      .then((res) => {
        if (cancelled) return
        setDonnees(res.data)
        setCorpsServi(debouncedKey)
      })
      .catch((err) => {
        if (cancelled) return
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        setErreur('Aperçu du pompage indisponible pour le moment.')
      })
      .finally(() => { if (!cancelled) setChargement(false) })
    return () => { cancelled = true; controller.abort() }
  }, [debouncedKey])

  return { donnees, chargement, erreur, corpsServi }
}

/** AGR212 — l'aperçu de l'économie DÉCLARÉE (AGR206, aucune écriture). */
export const postEconomiePompagePreview = (body, config = {}) =>
  api.post('/ventes/economie-pompage/preview/', body, config)

/**
 * AGR212 — même patron que `useEtudePompagePreview` : sert la garde de
 * cohérence (AGR204) au générateur. `corps` null = aucun appel.
 */
export function useEconomiePompagePreview(corps) {
  const corpsKey = corps ? JSON.stringify(corps) : null
  const debouncedKey = useDebouncedValue(corpsKey, 500)
  const [donnees, setDonnees] = useState(null)
  useEffect(() => {
    if (!debouncedKey) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète l'absence de corps
      setDonnees(null)
      return undefined
    }
    let cancelled = false
    const controller = new AbortController()
    setDonnees(null)
    postEconomiePompagePreview(JSON.parse(debouncedKey), { signal: controller.signal })
      .then((res) => { if (!cancelled) setDonnees(res.data) })
      .catch(() => {})
    return () => { cancelled = true; controller.abort() }
  }, [debouncedKey])
  return donnees
}
