import { useState } from 'react'

/**
 * AERR91 — état local qui SUIT une clé (id de la fiche affichée) : quand le
 * composant est re-rendu avec une AUTRE clé, l'état repart de `valeur`,
 * réinitialisé pendant le rendu (patron React « ajuster l'état quand une prop
 * change », sans effet). Renvoie `[etat, setEtat, cleChangee]` — `cleChangee`
 * est vrai le temps du rendu où la clé vient de changer (l'état servi est
 * encore l'ancien : lire `valeur` à sa place).
 */
export default function useEtatSuivi(cle, valeur) {
  const [etat, setEtat] = useState(valeur)
  const [cleVue, setCleVue] = useState(cle)
  const cleChangee = cleVue !== cle
  if (cleChangee) { setCleVue(cle); setEtat(valeur) }
  return [etat, setEtat, cleChangee]
}
