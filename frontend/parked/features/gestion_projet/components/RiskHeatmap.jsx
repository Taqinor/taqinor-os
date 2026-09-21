import { EmptyState } from '../../../ui'

/* ZPRJ8 — Matrice des risques P × I (heatmap 5×5). Compte les risques
   OUVERT/SURVEILLÉ par cellule (probabilité, impact) — les MAÎTRISÉ/CLOS sont
   exclus. Couleur de fond selon la criticité de la cellule (P × I). */

function toneFor(p, i) {
  const criticite = p * i
  if (criticite >= 15) return 'bg-destructive/70 text-destructive-foreground'
  if (criticite >= 8) return 'bg-warning/60 text-foreground'
  if (criticite > 0) return 'bg-warning/20 text-foreground'
  return 'bg-muted/30 text-muted-foreground'
}

export default function RiskHeatmap({ grille = [], topRisques = [] }) {
  if (!grille.length) {
    return <EmptyState title="Aucun risque actif" description="Aucun risque ouvert ou surveillé sur ce projet." />
  }

  const cellByKey = Object.fromEntries(
    grille.map((c) => [`${c.probabilite}-${c.impact}`, c.nombre]),
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto">
        <table className="border-collapse text-sm">
          <caption className="sr-only">Matrice des risques probabilité × impact</caption>
          <tbody>
            {[5, 4, 3, 2, 1].map((p) => (
              <tr key={p}>
                <th scope="row" className="w-10 pr-2 text-right text-xs font-medium text-muted-foreground">P{p}</th>
                {[1, 2, 3, 4, 5].map((i) => {
                  const nombre = cellByKey[`${p}-${i}`] ?? 0
                  return (
                    <td key={i} className="p-0.5">
                      <div
                        className={`flex size-14 items-center justify-center rounded-md text-sm font-semibold ${toneFor(p, i)}`}
                        title={`Probabilité ${p} × Impact ${i} — ${nombre} risque(s)`}
                      >
                        {nombre > 0 ? nombre : ''}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
            <tr>
              <th scope="row" className="w-10" />
              {[1, 2, 3, 4, 5].map((i) => (
                <td key={i} className="pt-1 text-center text-xs text-muted-foreground">I{i}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {topRisques.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium">Top risques par criticité</h4>
          <ul className="flex flex-col gap-1 text-sm">
            {topRisques.map((r) => (
              <li key={r.id} className="flex items-center gap-2">
                <span className="font-medium">{r.libelle}</span>
                <span className="text-xs text-muted-foreground">P{r.probabilite} × I{r.impact} = {r.criticite}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
