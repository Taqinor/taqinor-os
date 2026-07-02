import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WR9/FG26 — actions RGPD de la fiche client : export gaté responsable/admin,
   anonymisation admin uniquement derrière une confirmation AlertDialog. */

vi.mock('../../api/crmApi', () => ({
  default: {
    clientDataExport: vi.fn(() => Promise.resolve({ data: { identite: {} } })),
    anonymizeClient: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import crmApi from '../../api/crmApi'
import ClientRgpdActions from './ClientRgpdActions'

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderWithRole = (role, client = { id: 7, is_anonymized: false }, props = {}) => {
  const store = configureStore({
    reducer: { auth: (state = { role }) => state },
  })
  return render(
    <Provider store={store}>
      <ClientRgpdActions client={client} {...props} />
    </Provider>,
  )
}

describe('ClientRgpdActions (WR9/FG26)', () => {
  it("n'affiche rien pour un rôle non autorisé", () => {
    renderWithRole('normal')
    expect(screen.queryByTestId('rgpd-actions')).not.toBeInTheDocument()
  })

  it('responsable : export seulement, pas d\'anonymisation', () => {
    renderWithRole('responsable')
    expect(screen.getByRole('button', { name: /Export RGPD/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Anonymiser/ })).not.toBeInTheDocument()
  })

  it('admin : anonymisation derrière une confirmation AlertDialog', async () => {
    const onChanged = vi.fn()
    renderWithRole('admin', { id: 7, is_anonymized: false }, { onChanged })
    // Le POST n'est pas envoyé avant confirmation.
    fireEvent.click(screen.getByRole('button', { name: /Anonymiser \(RGPD\)/ }))
    expect(crmApi.anonymizeClient).not.toHaveBeenCalled()
    expect(await screen.findByText('Anonymiser ce client ?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Anonymiser définitivement' }))
    await waitFor(() => expect(crmApi.anonymizeClient).toHaveBeenCalledWith(7))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('client déjà anonymisé : pas de bouton anonymiser, mention affichée', () => {
    renderWithRole('admin', { id: 7, is_anonymized: true })
    expect(screen.queryByRole('button', { name: /Anonymiser/ })).not.toBeInTheDocument()
    expect(screen.getByText('Client anonymisé.')).toBeInTheDocument()
  })
})
