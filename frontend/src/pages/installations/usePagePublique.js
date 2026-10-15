import { useEffect, useState } from 'react'

/* Chargement PARTAGÉ des pages publiques à jeton (rapport d'intervention, suivi
   d'intervention) : `chargeur(token)` rend `{ data }` ; l'état passe de
   `loading` à `ok` (données reçues) ou `invalide` (jeton refusé / erreur). Rien
   n'est écrit une fois la page quittée. */
export function usePagePublique(chargeur, token) {
  const [etat, setEtat] = useState('loading') // loading|ok|invalide
  const [data, setData] = useState(null)

  useEffect(() => {
    let vivant = true
    chargeur(token)
      .then((res) => {
        if (!vivant) return
        setData(res.data || {})
        setEtat('ok')
      })
      .catch(() => { if (vivant) setEtat('invalide') })
    return () => { vivant = false }
  }, [chargeur, token])

  return { etat, data }
}
