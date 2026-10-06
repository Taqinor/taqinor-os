// CIQ223 — LE hook d'aperçu serveur partagé (C&I étude, C&I économie) :
// débondi, annulable en vol (AbortController + jeton `cancelled`), jamais
// périmé — le résultat est EFFACÉ au début de chaque appel et la réponse
// d'une saisie dépassée est jetée. `corps` = `null` ⇒ aucun appel.
// `appeler(body, {signal})` rend une promesse axios ; `corpsServi` nomme la
// saisie qui a produit `donnees`.
import { useEffect, useState } from 'react'
import { useDebouncedValue } from '../../../../lib/debounce'

export function useApercuServeur(corps, { appeler, erreurParDefaut, delai = 500 }) {
  const corpsKey = corps ? JSON.stringify(corps) : null
  const debouncedKey = useDebouncedValue(corpsKey, delai)
  const [donnees, setDonnees] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [corpsServi, setCorpsServi] = useState(null)
  // CIQ224 — le champ NOMMÉ par un 400 du serveur (`{detail, champ}`).
  const [erreurChamp, setErreurChamp] = useState(null)

  useEffect(() => {
    if (!debouncedKey) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète l'absence de corps
      setDonnees(null)
      setCorpsServi(null)
      setChargement(false)
      setErreur(null)
      setErreurChamp(null)
      return undefined
    }
    let body
    try { body = JSON.parse(debouncedKey) } catch { body = null }
    if (!body) return undefined

    let cancelled = false
    const controller = new AbortController()
    // `null` = l'API n'expose pas (encore) cet aperçu : aucun appel.
    const promesse = appeler(body, { signal: controller.signal })
    if (!promesse) return undefined
    setChargement(true)
    setErreur(null)
    setErreurChamp(null)
    setDonnees(null)
    setCorpsServi(null)
    promesse
      .then((res) => {
        if (cancelled) return
        setDonnees(res.data)
        setCorpsServi(debouncedKey)
      })
      .catch((err) => {
        if (cancelled) return
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        const detail = err?.response?.data?.detail
        setErreur(typeof detail === 'string' && detail ? detail : erreurParDefaut)
        setErreurChamp(err?.response?.data?.champ || null)
      })
      .finally(() => { if (!cancelled) setChargement(false) })
    return () => { cancelled = true; controller.abort() }
    // `appeler` est une référence stable (méthode de ventesApi) : seul le corps relance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedKey])

  return { donnees, chargement, erreur, erreurChamp, corpsServi, corpsKey }
}
