/* ============================================================================
   TCH77 — « AnneauProgression » : la progression de la journée, UNE seule forme (spec-8 §10,
   tour 2 : « Plus d'anneau, plus de camembert »). Le nom du composant reste celui de spec-7 §10 ;
   le rendu est celui des maquettes : `objectif` segments (12 × 6 px, 24 × 8 au bilan), un segment
   vert par tâche faite, la piste en `--tch-segment-vide`. Plafonné à 12 (l'objectif va de 1 à 12).
   Décoratif : le texte voisin (« 3 sur 5 ») porte l'information, d'où `aria-hidden`.
   Maquettes : ecran-aujourdhui-matin.html (repos), ecran-aujourdhui-15h.html, ecran-bilan.html (grand).
   ========================================================================== */
export default function AnneauProgression({ faites = 0, objectif = 0, grand = false }) {
  const total = Math.max(0, Math.min(12, Math.round(Number(objectif) || 0)))
  if (total === 0) return null
  return (
    <span className={grand ? 'segments grand' : 'segments'} aria-hidden="true" data-segments={total}>
      {Array.from({ length: total }, (_, rang) => <i key={rang} className={rang < faites ? 'fait' : undefined} />)}
    </span>
  )
}
