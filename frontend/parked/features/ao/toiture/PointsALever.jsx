/* AOF87 — Section « à lever au relevé d'exécution ».
   ----------------------------------------------------------------------------
   Elle ne se remplit PAS à la main : elle est dérivée des cotes (`pointsALever`).
   Toute cote déduite y entre — accompagnée de sa formule de déduction et de
   l'écart avec la valeur annoncée — et toute cote dont l'écart au plan/à
   l'annonce dépasse le seuil y entre aussi, même parfaitement mesurée : c'est
   l'ÉCART qui doit être publié.

   Le tableau est consultable et exportable (CSV français). La couleur reprend
   les tokens de provenance AOF9 : une cote déduite n'apparaît jamais en bleu. */
import { useCallback, useMemo } from 'react'
import { pointsALever, exporterPointsALever, coherentes } from './deduction'

const LIBELLE_PROVENANCE = {
  mesure: 'Mesuré',
  confirmer: 'À confirmer',
  deduit: 'Déduit du plan',
  devine: 'Deviné',
}

export default function PointsALever({ cotes = [], onExport }) {
  const points = useMemo(() => pointsALever(cotes), [cotes])
  // Invariant d'écran : si une cote déduite avait échappé à la bascule, on le
  // dit plutôt que de la rendre en bleu comme si de rien n'était.
  const fautives = useMemo(() => coherentes(cotes), [cotes])

  const exporter = useCallback(() => {
    onExport?.(exporterPointsALever(points))
  }, [onExport, points])

  return (
    <section className="ao-points-lever" data-ao-points-lever={points.length}>
      <h3>À lever au relevé d&apos;exécution</h3>
      <p className="ao-hint">
        Cette liste se remplit toute seule&nbsp;: une cote déduite d&apos;une fermeture, ou un
        écart avec la valeur annoncée, y entre sans intervention. La fermeture exacte fait foi.
      </p>

      {fautives.length > 0 && (
        <p role="alert" data-ao-points-lever-invariant>
          Anomalie&nbsp;: {fautives.length} cote(s) déduite(s) affichée(s) comme mesurée(s).
        </p>
      )}

      {points.length === 0 ? (
        <p data-ao-points-lever-vide>
          Aucun point à lever&nbsp;: toutes les cotes sont mesurées et conformes aux valeurs
          annoncées.
        </p>
      ) : (
        <>
          <table className="data-table">
            <caption>Points à lever ({points.length})</caption>
            <thead>
              <tr>
                <th scope="col">Repère</th>
                <th scope="col">Cote (m)</th>
                <th scope="col">Provenance</th>
                <th scope="col">Motif</th>
                <th scope="col">Écart</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.id} data-ao-point={p.id} data-ao-point-motif={p.motif}>
                  <th scope="row">{p.libelle}</th>
                  <td>{Number(p.valeur).toFixed(2)}</td>
                  <td
                    data-ao-point-provenance={p.provenance}
                    style={{ color: `var(--ao-provenance-${p.provenance}, currentColor)` }}
                  >
                    {LIBELLE_PROVENANCE[p.provenance] ?? p.provenance}
                  </td>
                  <td>
                    {p.motif === 'deduction' ? 'Cote déduite' : 'Écart avec la valeur annoncée'}
                    {p.formule ? ` — ${p.formule}` : ''}
                  </td>
                  <td>{p.texteEcart ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <button type="button" onClick={exporter} data-ao-points-lever-export>
            Exporter la liste (CSV)
          </button>
        </>
      )}
    </section>
  )
}
