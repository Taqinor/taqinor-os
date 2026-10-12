import { useState } from 'react'

/* État commun des écrans d'équipes de Paramètres (Équipes terrain WIR112,
   Équipes commerciales ZSAL3) : liste, chargement, erreur, nom de création et
   ligne occupée. Le chargement reste dans l'écran (sa liste et son API). */
export default function useEquipesAdmin() {
  const [equipes, setEquipes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [newNom, setNewNom] = useState('')
  const [busyId, setBusyId] = useState(null)
  return {
    equipes, setEquipes, loading, setLoading, error, setError,
    newNom, setNewNom, busyId, setBusyId,
  }
}
