import { useCallback, useEffect, useRef, useState } from 'react'

/* ============================================================================
   ARC45 — useResource(fetcher, params?, options?) : le fetch/état mutualisé.
   ----------------------------------------------------------------------------
   Chaque écran re-codait à la main loading / error / refetch (9 useState +
   useEffect, Promise.all brut, garde `alive`/`cancelled`…). Ce hook MAISON
   centralise ce cycle une fois pour toutes — AUCUNE dépendance (pas de
   react-query : l'option TanStack Query est une décision DEP séparée, non prise
   ici).

   Ce qu'il gère pour l'appelant :
     - `data`    : dernière réponse renvoyée par `fetcher` (transformée par
                   `options.select` si fourni), ou `options.initialData` avant
                   le premier chargement.
     - `loading` : vrai pendant un chargement en vol.
     - `error`   : message d'erreur (string) ou null. Personnalisable via
                   `options.errorMessage` (string ou (err) => string).
     - `refetch` : relance manuelle (retourne la promesse du chargement).

   Garanties :
     - ABORT AU DÉMONTAGE via un drapeau `mounted` (la couche api ne propage
       pas de `signal` — voir api/axios.js ; un AbortController serait donc
       inerte). Aucune mise à jour d'état après démontage.
     - PARAMS RÉACTIFS : un changement de `params` (comparé par sérialisation
       JSON stable) relance automatiquement le fetch ; les réponses périmées
       (montage précédent OU params changés en vol) sont ignorées.
     - `fetcher` reçoit `params` en argument : `fetcher(params)`. Il doit
       renvoyer une promesse dont la valeur résolue est passée telle quelle
       (ou via `select`) dans `data`. Pour un axios brut, passez
       `select: (res) => res.data`.

   Convention (à suivre pour TOUT nouvel écran de liste/tableau de bord) :
     const { data, loading, error, refetch } =
       useResource(() => monApi.truc(params), params, { select: (r) => r.data })
   `params` sert à la FOIS d'argument passé au fetcher ET de clé de réactivité :
   changez-le et le hook recharge. Passez `undefined`/`null` pour un chargement
   unique au montage.

   @param {(params:any) => Promise<any>} fetcher  Appel réseau ; reçoit `params`.
   @param {any} [params]  Paramètres réactifs (clé de refetch, arg du fetcher).
   @param {object} [options]
   @param {any}     [options.initialData=null]  Valeur de `data` avant chargement.
   @param {(value:any) => any} [options.select]  Transforme la valeur résolue.
   @param {string|((err:any) => string)} [options.errorMessage]
              Message d'erreur (défaut : 'Chargement impossible.').
   @param {boolean} [options.enabled=true]  Si faux, ne charge pas (data reste
              `initialData`, loading = false) ; repasser à vrai déclenche le fetch.
   ========================================================================== */

const DEFAULT_ERROR = 'Chargement impossible.'

function resolveError(errorMessage, err) {
  if (typeof errorMessage === 'function') {
    try {
      return errorMessage(err) || DEFAULT_ERROR
    } catch {
      return DEFAULT_ERROR
    }
  }
  return errorMessage || DEFAULT_ERROR
}

export default function useResource(fetcher, params, options = {}) {
  const {
    initialData = null,
    select,
    errorMessage,
    enabled = true,
  } = options

  const [data, setData] = useState(initialData)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState(null)

  // Sérialise les params pour une dépendance/clé stable (comme useComptaList).
  const key = JSON.stringify(params ?? null)

  // Refs pour lire la valeur courante sans re-créer `refetch` à chaque rendu.
  // Écrites dans un effet (jamais pendant le rendu) puis lues par `refetch`.
  const fetcherRef = useRef(fetcher)
  const paramsRef = useRef(params)
  const selectRef = useRef(select)
  const errorMessageRef = useRef(errorMessage)
  useEffect(() => {
    fetcherRef.current = fetcher
    paramsRef.current = params
    selectRef.current = select
    errorMessageRef.current = errorMessage
  })

  // Jeton de course : chaque chargement incrémente ce compteur ; seule la
  // réponse du dernier chargement lancé est prise en compte (les params ont pu
  // changer, ou le composant être démonté, entre-temps).
  const runIdRef = useRef(0)
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const refetch = useCallback(() => {
    if (!enabled) return Promise.resolve()
    const runId = ++runIdRef.current
    setLoading(true)
    setError(null)
    return Promise.resolve()
      .then(() => fetcherRef.current(paramsRef.current))
      .then((value) => {
        // Ignorer les réponses périmées (démontage ou nouveau chargement).
        if (!mountedRef.current || runId !== runIdRef.current) return
        const sel = selectRef.current
        setData(sel ? sel(value) : value)
      })
      .catch((err) => {
        if (!mountedRef.current || runId !== runIdRef.current) return
        setError(resolveError(errorMessageRef.current, err))
      })
      .finally(() => {
        if (!mountedRef.current || runId !== runIdRef.current) return
        setLoading(false)
      })
  // `key` capture le changement de params ; `enabled` (re)active le chargement.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled])

  // Chargement au montage + à chaque changement de params (via `refetch`).
  // Désactivé (`enabled:false`) : on n'appelle rien ; `loading` reste initialisé
  // à `enabled` au montage. Le drapeau `runIdRef` invalide le fetch en vol si les
  // params changent (ou au démontage).
  useEffect(() => {
    if (!enabled) return undefined
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage / au changement de params
    refetch()
    const runIdSnapshot = runIdRef
    return () => { runIdSnapshot.current++ }
  }, [refetch, enabled])

  return { data, loading, error, refetch }
}
