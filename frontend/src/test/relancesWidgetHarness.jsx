import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RelancesDuJourWidget from '../pages/crm/RelancesDuJourWidget'

/* Rendu COMMUN des suites du cockpit « Relances du jour » (ENF19). */
export function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}
