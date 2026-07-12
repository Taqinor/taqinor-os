import { useId } from 'react'

/* VX191 — `aria-activedescendant` id contract, partagé par les listes
   « champ texte → listbox avec curseur visuel » du repo (Combobox/MultiSelect/
   TimePicker le font déjà chacun en ligne depuis VX128 — ce hook ne les
   duplique pas, il donne juste aux prochains consommateurs (ProduitPicker,
   BcfProduitPicker, Composer @mention//slash, GlobalSearch…) le MÊME contrat
   d'id sans réimplémenter la génération à chaque fois). Chaque composant garde
   sa propre logique de curseur/navigation clavier (les formes divergent trop
   pour être mutualisées) ; seul l'id est standardisé ici.

   Usage :
     const { listId, getOptionId, activeId } = useActiveDescendant(cursor)
     <input aria-controls={listId} aria-activedescendant={activeId} />
     <ul id={listId} role="listbox">
       <li id={getOptionId(i)} role="option" aria-selected={i === cursor}>…</li> */
export function useActiveDescendant(activeIndex) {
  const listId = useId()
  const getOptionId = (index) => (index == null || index < 0 ? undefined : `${listId}-opt-${index}`)
  const activeId = getOptionId(activeIndex)
  return { listId, getOptionId, activeId }
}

export default useActiveDescendant
