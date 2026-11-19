/* ============================================================================
   Le squelette d'une liste de Tâches (deux sections de lignes « os », etat-chargement.html) : UN SEUL endroit porte ce
   balisage. Petit module SANS dépendance : `ui/ChargementTardif.jsx` (écrans) et `module.config.jsx` (repli de chargement
   d'un écran, dans le morceau commun du module) l'importent tous les deux sans rien tirer d'autre avec eux.
   La classe est `squelette-liste` (pas `.squelette` : le bloc d'UNE barre de 44 px de saisie.css).
   ========================================================================== */

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

/** Le squelette entier, annoncé « Chargement ». */
export default function SqueletteListe() {
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
