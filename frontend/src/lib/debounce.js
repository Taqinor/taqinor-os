import { useEffect, useState } from 'react'

/* O66 — Anti-rebond (debounce) sans dépendance externe.
   ----------------------------------------------------------------------------
   `debounce(fn, ms)` retourne une fonction qui ne déclenche `fn` qu'après `ms`
   millisecondes SANS nouvel appel (appel « trailing »). Chaque appel reporte
   l'échéance. Utile pour ne pas recalculer un filtre à chaque frappe sur les
   grandes listes. `cancel()` annule l'appel en attente.

   Fonction PURE (aucun React) → testable sous `node --test`. */
export function debounce(fn, ms = 200) {
  let timer = null
  function debounced(...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, ms)
  }
  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }
  return debounced
}

/* Hook React : renvoie `value` mais SEULEMENT après `ms` ms de stabilité.
   Permet d'afficher une saisie instantanée tout en n'appliquant le filtre
   (recherche, requête) qu'après une courte pause de frappe. */
export function useDebouncedValue(value, ms = 200) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}

export default debounce
