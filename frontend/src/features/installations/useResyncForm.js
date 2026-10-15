import { useEffect, useRef } from 'react'

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
