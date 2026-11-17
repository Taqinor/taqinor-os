import { Star } from 'lucide-react'

/* ============================================================================
   TCH44 — Étoile « Essentielle » : 1 à 3 tâches par jour (★), sur Essentiel et Prévu
   seulement. Deux formes :
     · sans `onBasculer` : le repère de fin de ligne des maquettes (étoile pleine, or) ;
     · avec `onBasculer` : un bouton à cocher de 44 px (Essentiel / Prévu, « Touche ★ pour
       ton essentiel »), état lu par le lecteur d'écran.
   La 4e est REFUSÉE : si `nbEssentielles` a déjà atteint `max` (3) et que cette étoile
   n'est pas posée, rien ne change côté serveur — `onRefus()` est appelé (le parent annonce
   « 3 au plus. », textes.md §2.15) et `aria-live` n'est pas touché ici.
   Maquette : docs/taches/maquettes/composants-1.html (Essentielle).
   ========================================================================== */
export default function Etoile({
  active = false,
  onBasculer,
  nbEssentielles = 0,
  max = 3,
  onRefus,
  titre = '',
}) {
  if (!onBasculer) {
    return active ? <Star className="i i-16 etoile" aria-label="Essentielle" role="img" /> : null
  }
  const basculer = () => {
    if (!active && nbEssentielles >= max) {
      onRefus?.()
      return
    }
    onBasculer(!active)
  }
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={active}
      aria-label={titre ? `Essentielle : ${titre}` : 'Essentielle'}
      className={active ? 'etoile-bouton active' : 'etoile-bouton'}
      onClick={basculer}
    >
      <Star className={active ? 'i i-16 etoile' : 'i i-16'} aria-hidden="true" />
    </button>
  )
}
