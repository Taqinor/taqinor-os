import { useCallback, useEffect, useRef, useState } from 'react'
import { runOptimistic } from '../lib/optimistic'

/**
 * L151 — useOptimisticSave(serverValue, options)
 *
 * Couche React au-dessus de `runOptimistic` (lib/optimistic) pour un edit inline
 * optimiste avec rollback. Pensée « Redux-friendly » : la fonction `commit`
 * passée à `save()` est l'appel réseau réel — typiquement
 * `() => dispatch(updateLead(...)).unwrap()` — qui REJETTE en cas d'échec ; le
 * hook applique alors le rollback tout seul. N'utilise que des endpoints
 * existants (aucune migration).
 *
 * Ce qu'il gère pour l'appelant :
 *   - `value`        : valeur AFFICHÉE — optimiste pendant l'enregistrement,
 *                      valeur serveur confirmée sinon, ancienne valeur restaurée
 *                      au rollback.
 *   - `status`       : 'idle' | 'saving' | 'saved' | 'error'.
 *   - `statusLabel`  : libellé FR inline ('' / 'Enregistrement…' / 'Enregistré').
 *   - `isSaving`     : raccourci booléen.
 *   - `error`        : dernière erreur (ou null).
 *   - `rowProps`     : affordance « ligne en cours » à étaler sur la ligne —
 *                      ~50 % d'opacité + aria-busy + data-saving (pour rendre un
 *                      spinner). Vide au repos.
 *   - `save(next, commit)` : applique `next` en optimiste puis `commit(next)`.
 *                      Ne rejette jamais : renvoie { ok, data?, error? }.
 *
 * @param {*} serverValue  Valeur confirmée côté serveur (suivie au changement).
 * @param {object} [options]
 * @param {number} [options.savedDuration=2000] Durée (ms) du badge « Enregistré »
 *                 avant retour au repos. 0 = persistant.
 * @param {Function} [options.onError] (error) => void, appelé après le rollback.
 */
export function useOptimisticSave(serverValue, options = {}) {
  const { savedDuration = 2000, onError } = options

  // Valeur affichée. Suit `serverValue` au repos via le motif officiel
  // « ajuster l'état au changement de prop » (setState au rendu, pas d'effet).
  const [value, setValue] = useState(serverValue)
  const [prevServer, setPrevServer] = useState(serverValue)
  const [status, setStatus] = useState('idle') // idle | saving | saved | error
  const [error, setError] = useState(null)

  // Pendant un enregistrement on NE resynchronise pas sur serverValue (sinon on
  // écraserait la valeur optimiste affichée). Hors enregistrement, on suit.
  if (serverValue !== prevServer && status !== 'saving') {
    setPrevServer(serverValue)
    setValue(serverValue)
  }

  // Timer du badge « Enregistré » — nettoyé au démontage / nouveau save.
  const savedTimer = useRef(null)
  const clearSavedTimer = () => {
    if (savedTimer.current) {
      clearTimeout(savedTimer.current)
      savedTimer.current = null
    }
  }
  useEffect(() => clearSavedTimer, [])

  const save = useCallback(
    (next, commit) => {
      if (typeof commit !== 'function') {
        throw new Error('useOptimisticSave: save(next, commit) — `commit` requis')
      }
      clearSavedTimer()
      setError(null)
      setStatus('saving')

      // `runOptimistic` applique la valeur optimiste, lance le commit, et
      // restaure l'ancienne valeur si le commit rejette. Ne rejette jamais.
      return runOptimistic({
        current: value,
        optimistic: next,
        apply: setValue,
        commit: () => commit(next),
        onError: (err) => {
          if (typeof onError === 'function') {
            try { onError(err) } catch { /* l'effet d'erreur ne masque rien */ }
          }
        },
      }).then((res) => {
        if (res.ok) {
          // Confirmé : on GARDE la valeur optimiste affichée (le store parent
          // poussera la nouvelle serverValue à son tour ; `prevServer` ne suit
          // que la prop serverValue, jamais l'optimiste, pour ne pas
          // resynchroniser à tort).
          setStatus('saved')
          if (savedDuration > 0) {
            savedTimer.current = setTimeout(() => {
              savedTimer.current = null
              setStatus('idle')
            }, savedDuration)
          }
        } else {
          // Rollback déjà fait par runOptimistic ; on reflète l'échec.
          setError(res.error)
          setStatus('error')
        }
        return res
      })
    },
    // `value` est lu pour fixer le point de rollback ; il est stable hors save.
    [value, onError, savedDuration],
  )

  const isSaving = status === 'saving'

  const STATUS_LABELS = { saving: 'Enregistrement…', saved: 'Enregistré' }
  const statusLabel = STATUS_LABELS[status] ?? ''

  // Affordance « ligne en cours » : ~50 % d'opacité + occupé pendant le save.
  const rowProps = {
    'aria-busy': isSaving,
    'data-saving': isSaving,
    className: isSaving ? 'opacity-50 transition-opacity pointer-events-none' : '',
  }

  return { value, status, statusLabel, isSaving, error, rowProps, save }
}

export default useOptimisticSave
