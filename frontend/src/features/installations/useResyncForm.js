import { useEffect, useRef, useState } from 'react'

/* ACHT57 / ACHT102 — resynchronise un formulaire sur sa valeur serveur après
   chaque rafraîchissement : un champ NON touché suit la nouvelle valeur
   serveur, un champ édité par l'utilisateur garde sa saisie. Le diff envoyé se
   calcule contre `initial`, donc un champ périmé n'est jamais renvoyé.
   UNE seule implémentation pour les formulaires `fields` et `mes` de la fiche
   chantier. */
export function useResyncForm(initial, setForm) {
  const cle = JSON.stringify(initial)
  const base = useRef(cle)
  useEffect(() => {
    if (base.current === cle) return
    const ancien = JSON.parse(base.current)
    base.current = cle
    setForm((f) => Object.fromEntries(Object.keys(initial).map(
      (k) => [k, JSON.stringify(f[k]) === JSON.stringify(ancien[k]) ? initial[k] : f[k]])))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `cle` encode `initial` : seul son changement resynchronise (ACHT57, D-ENF22)
  }, [cle])
}

export default useResyncForm

/**
 * AERR91 — état local qui SUIT une clé (id de la fiche affichée) : quand le
 * composant est re-rendu avec une AUTRE clé, l'état repart de `valeur`,
 * réinitialisé pendant le rendu (patron React « ajuster l'état quand une prop
 * change », sans effet). Renvoie `[etat, setEtat, cleChangee]` — `cleChangee`
 * est vrai le temps du rendu où la clé vient de changer (l'état servi est
 * encore l'ancien : lire `valeur` à sa place).
 */
export function useEtatSuivi(cle, valeur) {
  const [etat, setEtat] = useState(valeur)
  const [cleVue, setCleVue] = useState(cle)
  const cleChangee = cleVue !== cle
  if (cleChangee) { setCleVue(cle); setEtat(valeur) }
  return [etat, setEtat, cleChangee]
}
