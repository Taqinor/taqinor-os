import { useState } from 'react'

/* Filtres « saisie → appliquer » + page courante, partagés par les listes
   paginées des Paramètres (Corbeille, Pièces jointes). Appliquer / réinitialiser
   repartent toujours de la page 1. Un seul endroit — jamais recopié. */
export function useFiltresPaginees(vides) {
  const [saisie, setSaisie] = useState(vides)
  const [filtres, setFiltres] = useState(vides)
  const [page, setPage] = useState(1)

  const appliquer = (e) => {
    e.preventDefault()
    setPage(1)
    setFiltres(saisie)
  }

  const reinitialiser = () => {
    setPage(1)
    setSaisie(vides)
    setFiltres(vides)
  }

  const set = (cle) => (e) => setSaisie((p) => ({ ...p, [cle]: e.target.value }))

  return { saisie, filtres, page, setPage, appliquer, reinitialiser, set }
}
