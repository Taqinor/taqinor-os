// CCAT103 — Paramètres › Devis › « Prestations C&I » en tableau compact : une
// ligne par prestation, en-têtes une seule fois ; sous 640 px, une carte par
// prestation. Mêmes ids (pe-ci-<cle>-<champ>), mêmes data-testid, même état
// (`forfaits_ci`) que l'ancien rendu à 5 champs répétés par prestation.
import { Input } from '../../ui'
import { PRESTATIONS_CI, MONTANTS_FORFAIT_CI, _rempli, sourceManquante, MSG_SOURCE } from './peConstants'

const ENTETES = ['Prestation', ...MONTANTS_FORFAIT_CI.map(([, l]) => l), 'Source', 'Date']
// Mobile d'abord (carte) ; à partir de 640 px les mêmes balises redeviennent un tableau.
const TD = 'block px-0 py-1 sm:table-cell sm:px-2 sm:py-1.5 sm:align-top'
const LIBELLE_MOBILE = 'mb-0.5 block text-[11px] text-muted-foreground sm:hidden'

function Cellule({ titre, children }) {
  return (
    <td className={TD}>
      <span className={LIBELLE_MOBILE} aria-hidden="true">{titre}</span>
      {children}
    </td>
  )
}

/** `forfaits` = `form.forfaits_ci` ; `onChange(cle, champ, valeur)` = setForfaitCi. */
export default function PrestationsCiTable({ forfaits, onChange }) {
  return (
    <div className="sm:overflow-x-auto" data-testid="prestations-ci">
      <table className="block w-full text-left sm:table">
        <thead className="sr-only sm:not-sr-only sm:table-header-group">
          <tr className="sm:table-row">
            {ENTETES.map((titre) => (
              <th key={titre} scope="col"
                  className="px-2 py-1.5 text-[11px] font-semibold text-muted-foreground">
                {titre}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="block sm:table-row-group">
          {PRESTATIONS_CI.map(([cle, libelle]) => {
            const f = (forfaits || {})[cle] || {}
            const sansSource = sourceManquante(f, MONTANTS_FORFAIT_CI)
            const vide = !MONTANTS_FORFAIT_CI.some(([k]) => _rempli(f[k]))
            return (
              <tr key={cle} data-testid={`prestation-ci-${cle}`}
                  className="mb-2 block rounded-lg border border-border p-2 sm:mb-0 sm:table-row sm:rounded-none sm:border-0 sm:border-t sm:p-0">
                <th scope="row" className={`${TD} text-[11px] font-semibold text-muted-foreground`}>
                  {libelle}
                  {vide && <span className="ml-2 font-normal italic">prix à renseigner</span>}
                </th>
                {MONTANTS_FORFAIT_CI.map(([k, lbl]) => (
                  <Cellule key={k} titre={lbl}>
                    <Input id={`pe-ci-${cle}-${k}`} type="number" step="any"
                           aria-label={`${libelle} — ${lbl}`}
                           value={f[k] ?? ''}
                           onChange={e => onChange(cle, k, e.target.value)} />
                  </Cellule>
                ))}
                <Cellule titre="Source">
                  <Input id={`pe-ci-${cle}-source`}
                         aria-label={`${libelle} — source`}
                         value={f.source ?? ''}
                         aria-invalid={sansSource}
                         onChange={e => onChange(cle, 'source', e.target.value)} />
                  {sansSource && (
                    <p role="alert" className="text-[11px] text-destructive">{MSG_SOURCE}</p>
                  )}
                </Cellule>
                <Cellule titre="Date">
                  <Input id={`pe-ci-${cle}-date`} type="date"
                         aria-label={`${libelle} — date`}
                         value={f.date ?? ''}
                         onChange={e => onChange(cle, 'date', e.target.value)} />
                </Cellule>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
