import { COURBES_REPERE } from './SunDiagram.helpers'

/* Légende PARTAGÉE des diagrammes de course du soleil (CourseSoleil,
   HorizonPanel) : une pastille par courbe repère, puis l'horizon (`libelleHorizon`
   dit sa nature) et les éventuels marqueurs en plus (`children`). */
export function LegendeCourbes({ libelleHorizon, children }) {
  return (
    <div className="mt-1 flex flex-wrap gap-3 text-xs text-lune-faint">
      {COURBES_REPERE.map((c) => (
        <span key={c.jour} className="inline-flex items-center gap-1">
          <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 2, background: c.couleur }} />
          {c.label}
        </span>
      ))}
      <span className="inline-flex items-center gap-1">
        <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 10, background: 'rgba(90,60,30,0.55)' }} />
        {libelleHorizon}
      </span>
      {children}
    </div>
  )
}
