import { useState } from 'react'
import { messageServeur } from '../../../features/stock/api/erreurs'

/* ASTK220/ASTK224 — « un geste » des écrans entrepôt : appelle l'action,
   affiche l'éventuel message de succès, RELIT le serveur (`recharger`) et
   affiche l'erreur serveur mot pour mot. Un seul endroit (garde de duplicat
   littéral). Renvoie `{ occupe, geste }` ; `geste(action, repli, succes)`
   résout à true / false. */
export default function useGesteEcran(recharger, setErreur, setInfo) {
  const [occupe, setOccupe] = useState(false)

  const geste = async (action, repli, succes) => {
    setOccupe(true); setErreur(null); setInfo(null)
    try {
      await action()
      if (succes) setInfo(succes)
      await recharger()
      return true
    } catch (err) {
      setErreur(messageServeur(err, repli))
      return false
    } finally { setOccupe(false) }
  }

  return { occupe, geste }
}
