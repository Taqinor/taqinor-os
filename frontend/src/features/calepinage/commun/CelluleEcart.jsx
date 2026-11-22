import { nombre } from './mesuresMensuelles'

/** La cellule « écart » d'un mois : « — » tant que le serveur n'en sert pas (jamais 0). */
export default function CelluleEcart({ ecart, testId }) {
  return (
    <td data-testid={testId}>
      {ecart === null || ecart === undefined ? '—' : `${nombre(ecart, true)} %`}
    </td>
  )
}
