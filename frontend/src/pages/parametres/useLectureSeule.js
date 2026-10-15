import { useEffect, useState } from 'react'

/* Chargement commun des pages Paramètres « Fiabilité » en lecture seule
   (État des dépendances, Rapport SLA, Limites & usage) : donnée, état de
   chargement et message d'erreur. `charger` renvoie la promesse axios ;
   `vide` remplace une réponse sans donnée. */
export default function useLectureSeule(charger, initial, vide, messageErreur) {
  const [data, setData] = useState(initial)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let active = true
    charger()
      .then((r) => { if (active) setData(r.data ?? vide) })
      .catch(() => { if (active) setErreur(messageErreur) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement au montage seulement (D-ENF22)
  }, [])

  return { data, loading, erreur }
}
