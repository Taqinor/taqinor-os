/* Maquette Main (22/11) — pictogrammes de la barre d'outils de la carte et de la pile de zoom (tracés
   de la maquette, trait `currentColor`, 24 × 24). Doublure locale en attendant leur entrée dans
   `coque/primitives.jsx::Icone` (demande à l'orchestrateur, journal L1). */
const TRACES = {
  selection: <path d="M5 3l14 8-6 2-2 6z" />,
  trace: (
    <>
      <path d="M4 18l5-12 6 9 5-7" />
      <circle cx="4" cy="18" r="1.6" /><circle cx="9" cy="6" r="1.6" />
      <circle cx="15" cy="15" r="1.6" /><circle cx="20" cy="8" r="1.6" />
    </>
  ),
  obstacle: <><rect x="5" y="5" width="14" height="14" rx="2" /><path d="M5 19L19 5" /></>,
  mesure: <><path d="M3 17L17 3l4 4L7 21z" /><path d="M8 12l2 2M11 9l2 2M14 6l2 2" /></>,
  annuler: <><path d="M9 14L4 9l5-5" /><path d="M4 9h10a6 6 0 010 12h-3" /></>,
  retablir: <><path d="M15 14l5-5-5-5" /><path d="M20 9H10a6 6 0 000 12h3" /></>,
  pleinEcran: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
}

export default function PictoToit({ nom, taille = 20 }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{TRACES[nom] ?? null}</svg>
  )
}
