import './relancesSuiviMocks'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RelancesSuiviPage from '../pages/crm/RelancesSuiviPage'

/* Rendu COMMUN des suites « Suivi des relances » (ENF19). */
export function mount() {
  return render(
    <MemoryRouter>
      <RelancesSuiviPage />
    </MemoryRouter>,
  )
}
