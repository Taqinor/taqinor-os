// ACAL345 — UN seul hook d'aperçu serveur debouncé (~500 ms), annulable en vol
// (race token `cancelled` + AbortController), partagé par l'aperçu du moteur
// horaire et par l'aperçu du pompage au lieu d'être recopié.
//
// `corps` : objet JSON à envoyer ; `null` = rien à demander (aucun appel,
// `donnees` reste `null`). `appeler(body, { signal })` retourne la promesse
// de l'appel réseau, ou `null` quand l'appel est indisponible (dégradation
// silencieuse). Ne lève jamais et n'expose jamais un résultat périmé :
// `donnees` est effacé au début de chaque nouvel appel.
import { useEffect, useState } from 'react'
import { useDebouncedValue } from './debounce'

export function useApercuServeur(corps, appeler, messageErreur) {
  const corpsKey = corps ? JSON.stringify(corps) : null
  const debouncedKey = useDebouncedValue(corpsKey, 500)
  const [donnees, setDonnees] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState(null)
  // Clé du corps qui a produit `donnees` (l'appelant compare pour ne jamais
  // appliquer la réponse d'un ANCIEN corps).
  const [corpsServi, setCorpsServi] = useState(null)
  // Clé RÉELLEMENT envoyée / dont la requête a ÉCHOUÉ (QJR644).
  const [corpsEnVol, setCorpsEnVol] = useState(null)
  const [corpsEchoue, setCorpsEchoue] = useState(null)

  useEffect(() => {
    if (!debouncedKey) {
      // UNE seule dérogation par bloc : la règle ne signale que le PREMIER
      // setState, et une par ligne déclencherait `reportUnusedDisableDirectives`.
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète l'absence d'ancrage
      setDonnees(null)
      setCorpsServi(null)
      setCorpsEnVol(null)
      setCorpsEchoue(null)
      setChargement(false)
      setErreur(null)
      return undefined
    }
    let body
    try { body = JSON.parse(debouncedKey) } catch { body = null }
    if (!body) return undefined

    const controller = new AbortController()
    const requete = appeler(body, { signal: controller.signal })
    if (!requete) return undefined
    let cancelled = false
    // Jamais de résultat périmé pendant le recalcul : on efface avant l'appel.
    setChargement(true)
    setErreur(null)
    setDonnees(null)
    setCorpsServi(null)
    setCorpsEnVol(debouncedKey)
    setCorpsEchoue(null)
    requete
      .then((res) => {
        if (cancelled) return
        setDonnees(res.data)
        setCorpsServi(debouncedKey)
      })
      .catch((err) => {
        if (cancelled) return
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        setErreur(messageErreur)
        setCorpsEchoue(debouncedKey)
      })
      .finally(() => { if (!cancelled) setChargement(false) })
    return () => { cancelled = true; controller.abort() }
    // `appeler` / `messageErreur` sont des constantes de module côté appelants.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedKey])

  return { donnees, chargement, erreur, corpsServi, corpsEnVol, corpsEchoue }
}
