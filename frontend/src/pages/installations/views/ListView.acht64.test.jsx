import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import installationsReducer from '../../../features/installations/store/installationsSlice'

/* ACHT64 — l'action groupée « Changer le statut » distingue modifiés / refusés
   (avec la raison du serveur) / inchangés, avec UNE seule relecture en fin de
   lot. Composant réel (InstallationsPage + ListView) devant un faux serveur qui
   renvoie le 400 réel `{statut: [raison]}` des chantiers sans acompte. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => {
      const kids = Array.isArray(children) ? children : [children]
      const label = kids.find((c) => c && c.props && c.props['aria-label'])?.props?.['aria-label']
      return (
        <select role="combobox" aria-label={label} value={value ?? ''}
                onChange={(e) => onValueChange(e.target.value)}>
          <option value="" />
          {children}
        </select>
      )
    },
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

const RAISON = 'Planification refusée : l’acompte n’a pas été reçu.'
const serveur = vi.hoisted(() => ({ lectures: 0, patchs: [] }))

vi.mock('../../../api/installationsApi', () => ({
  default: {
    getInstallations: () => {
      serveur.lectures += 1
      return Promise.resolve({ data: { count: 4, results: [
        { id: 1, reference: 'CH-A1', client_nom: 'A', statut: 'materiel_commande' },
        { id: 2, reference: 'CH-A2', client_nom: 'B', statut: 'materiel_commande' },
        { id: 3, reference: 'CH-A3', client_nom: 'C', statut: 'materiel_commande' },
        { id: 4, reference: 'CH-A4', client_nom: 'D', statut: 'planifie' },
      ] } })
    },
    updateInstallation: (id, data) => {
      serveur.patchs.push({ id, data })
      return Promise.reject({ response: { data: { statut: [RAISON] } } })
    },
  },
}))
vi.mock('../../../api/crmApi', () => ({
  default: { getAssignableUsers: () => Promise.resolve({ data: [] }) },
}))

import InstallationsPage from '../InstallationsPage'

const rendre = () => render(
  <Provider store={configureStore({
    reducer: {
      installations: installationsReducer,
      auth: (s = { user: { id: 1 } }) => s,
      stock: (s = { produits: [] }) => s,
    },
  })}>
    <MemoryRouter initialEntries={['/chantiers']}>
      <ThemeProvider><InstallationsPage /></ThemeProvider>
    </MemoryRouter>
  </Provider>,
)

afterEach(() => {
  cleanup()
  serveur.lectures = 0
  serveur.patchs = []
  try { localStorage.clear() } catch { /* indisponible */ }
})

describe('ListView — action groupée ACHT64', () => {
  it('un lot entièrement refusé le dit, avec la raison, et relit la liste une fois', async () => {
    const user = userEvent.setup()
    rendre()
    await waitFor(() => expect(screen.getAllByText('CH-A1').length).toBeGreaterThan(0))
    await user.click(screen.getAllByLabelText('Tout sélectionner sur cette page')[0])
    await user.click(await screen.findByRole('button', { name: /Changer le statut/ }))

    await user.selectOptions(await screen.findByLabelText('Nouveau statut'), 'planifie')
    expect(await screen.findByText(/3 seront modifiés, 1 déjà à ce statut/)).toBeInTheDocument()

    const lecturesAvant = serveur.lectures
    await user.click(screen.getByRole('button', { name: 'Appliquer' }))

    const bilan = await screen.findByTestId('bulk-result')
    expect(bilan).toHaveTextContent('0 mis à jour, 3 refusés')
    expect(bilan).toHaveTextContent(RAISON)
    expect(bilan).not.toHaveTextContent(/3 chantier\(s\) mis à jour/)
    expect(serveur.patchs).toHaveLength(3)
    await waitFor(() => expect(serveur.lectures - lecturesAvant).toBe(1))
  })
})
