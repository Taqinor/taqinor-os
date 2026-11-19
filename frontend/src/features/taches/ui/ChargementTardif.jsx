import { useEffect, useState } from 'react'

/* ============================================================================
   Raccord F2 — l'état « chargement » commun aux écrans de Tâches (spec-7 « Partout » : squelette, jamais sur une liste
   déjà affichée ; textes.md §2.19 : annonce « Chargement »). L'écran le monte tant qu'il n'a RIEN à montrer.
   R4-42 — la classe est `squelette-liste` : `.squelette` est le bloc d'UNE barre de 44 px de saisie.css (fiche, bilan) ; sous elle ce
   squelette de liste tenait dans 44 px de haut et la page se posait PAR-DESSUS (Projets n'affichait que « Nouveau projet »).
   R2-089 — dès 300 ms (une réponse rapide ne fait rien clignoter ; au-delà, l'écran montre déjà SA forme) : deux
   sections de lignes de tâches « os », comme etat-chargement.html — jamais le squelette des tableaux de bord de l'ERP.
   ========================================================================== */

const DELAI_MS = 300
const SECTIONS = [
  [['72%', '44%'], ['84%', '38%'], ['64%', '']],
  [['78%', '48%'], ['56%', '40%']],
]

/** Une ligne « os » du squelette (case, une ou deux barres) — partagée avec le squelette d'Aujourd'hui. */
export function LigneOs({ l1, l2 = '' }) {
  return (
    <div className="ligne" aria-hidden="true">
      <span className="case"><span className="os cercle" /></span>
      <div className="ligne-corps">
        <span className="os l1" style={{ width: l1 }} />
        {l2 ? <span className="os l2" style={{ width: l2 }} /> : null}
      </div>
      <div className="ligne-fin" />
    </div>
  )
}

export default function ChargementTardif({ actif = true }) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    if (!actif) return undefined
    const minuteur = setTimeout(() => setVisible(true), DELAI_MS)
    return () => { clearTimeout(minuteur); setVisible(false) }
  }, [actif])
  if (!actif || !visible) return null
  return (
    <div className="squelette-liste" role="status" aria-label="Chargement">
      {SECTIONS.map((lignes, section) => (
        <div key={section} className="squelette-section">
          <span className="os titre-section" aria-hidden="true" />
          {lignes.map(([l1, l2], rang) => <LigneOs key={rang} l1={l1} l2={l2} />)}
        </div>
      ))}
    </div>
  )
}
