import { useState } from 'react'

/* ============================================================================
   TCH44 — Case ronde : 22 px visibles dans une cible de 44 px (spec-8 §2). Cocher =
   le rond se remplit (0,8 → 1,08 → 1) et la coche se trace, 180 ms décélérée ; le titre
   se barre en même temps (classe `faite` de la ligne). Mouvement réduit : état final.
   Maquette : docs/taches/maquettes/composants-4.html (états Repos, Survol, Pressée,
   Cochée, En attente, Sélection, Clavier, Hors ligne).

   Optimiste : la case bascule AU TOUCHER (< 0,1 s) ; si `onBasculer(suivant)` rejette
   (échec réseau), elle REVIENT à son état d'avant. Tant que le parent ne change pas
   `coche`, l'état optimiste est gardé ; dès que `coche` change, la prop reprend la main.
   ========================================================================== */
export default function CaseRonde({
  coche = false,
  onBasculer,
  titre = '',
  libelle,
  attente = false,
  selection = false,
  desactivee = false,
}) {
  const [local, setLocal] = useState(null)
  const [anime, setAnime] = useState(false)
  const [cochePrecedente, setCochePrecedente] = useState(coche)
  // la prop reprend la main dès qu'elle change (réglage d'état pendant le rendu, jamais dans un effet)
  if (cochePrecedente !== coche) {
    setCochePrecedente(coche)
    setLocal(null)
  }
  const valeur = local ?? coche

  const basculer = async () => {
    if (desactivee) return
    const suivant = !valeur
    setLocal(suivant)
    setAnime(suivant)
    try {
      await onBasculer?.(suivant)
    } catch {
      // échec : retour arrière, la ligne reste comme avant le toucher
      setLocal(null)
      setAnime(false)
    }
  }

  const nom = libelle
    ?? (selection ? `${valeur ? 'Sélectionnée' : 'Sélectionner'} : ${titre}` : `Marquer « ${titre} » comme faite`)

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={valeur}
      aria-label={nom}
      aria-disabled={desactivee || undefined}
      disabled={desactivee}
      className={['case', attente ? 'attente' : '', selection ? 'selection' : ''].filter(Boolean).join(' ')}
      onClick={basculer}
    >
      <span className={anime ? 'rond coche-anime' : 'rond'}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
      </span>
    </button>
  )
}
