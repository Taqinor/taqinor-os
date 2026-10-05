// ACAL199 — un clic sur un résultat « Calepinages » ouvre /calepinage/<id>
// (avant : ROUTE.calepinage absent, la barre se fermait sans naviguer).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../../api/reportingApi', () => ({
  default: { search: vi.fn() },
}))

import reportingApi from '../../api/reportingApi'
import GlobalSearch from './GlobalSearch'
import { reponseContrat } from '../../test/fixtures/contractSamples'

function Lieu() {
  const l = useLocation()
  return <span data-testid="lieu">{l.pathname}</span>
}

function renderSearch({ modulesDesactives = [] } = {}) {
  const store = configureStore({
    reducer: {
      auth: (s = { role: 'admin', permissions: [], modulesDesactives, user: null }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <GlobalSearch />
        <Routes><Route path="*" element={<Lieu />} /></Routes>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ACAL199 — recherche globale : groupe Calepinages', () => {
  beforeEach(() => {
    reportingApi.search.mockReset()
    reportingApi.search.mockResolvedValue(reponseContrat('reporting', 'recherche_types'))
  })
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('clic sur un calepinage navigue vers /calepinage/7', async () => {
    renderSearch()
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'hammadi' } })
    const ligne = await screen.findByText('Villa Hammadi')
    fireEvent.click(ligne)
    expect(screen.getByTestId('lieu')).toHaveTextContent('/calepinage/7')
  })

  it('app calepinage désactivée : le groupe est masqué', async () => {
    renderSearch({ modulesDesactives: ['calepinage'] })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'hammadi' } })
    await new Promise((r) => setTimeout(r, 400))
    expect(screen.queryByText('Villa Hammadi')).not.toBeInTheDocument()
  })
})
