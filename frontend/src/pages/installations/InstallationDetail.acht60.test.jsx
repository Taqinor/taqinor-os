import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ACHT60 — dérogations émises depuis la fiche chantier : « Motif (acompte non
   reçu) » → motif_override_acompte, « Motif de réouverture » → motif_reouverture,
   et « Marquer réceptionné » seulement depuis « Installé ». Faux serveur en
   mémoire qui applique les règles réelles (400 sans motif, 200 avec). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children, disabled }) => {
      const kids = Array.isArray(children) ? children : [children]
      const id = kids.find((c) => c && c.props && c.props.id)?.props?.id
      return (
        <select role="combobox" id={id} value={value ?? ''} disabled={disabled}
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

vi.mock('./ChantierGateTimeline', () => ({ default: () => null }))
vi.mock('./ChantierChecklist', () => ({ default: () => null }))
vi.mock('../../features/installations/offline/OfflineSyncIndicator', () => ({
  default: () => null,
}))

const db = {}
vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
    getInstallation: (id) => Promise.resolve({ data: { ...db[id] } }),
    updateInstallation: (id, body) => {
      const row = db[id]
      if (body.statut && body.statut !== row.statut) {
        if (body.statut === 'planifie' && !body.motif_override_acompte) {
          return Promise.reject({ response: { data: { statut: [
            'Planification refusée : l’acompte n’est pas encore reçu.'] } } })
        }
        if (row.statut === 'cloture' && !body.motif_reouverture) {
          return Promise.reject({ response: { data: { statut: [
            'Ce chantier est CLÔTURÉ : sa réouverture exige un motif explicite.'] } } })
        }
        row.statut = body.statut
      }
      return Promise.resolve({ data: { ...row } })
    },
  },
}))
vi.mock('../../api/savApi', () => ({
  default: {
    getEquipements: () => Promise.resolve({ data: [] }),
    getTickets: () => Promise.resolve({ data: [] }),
    getContrats: () => Promise.resolve({ data: [] }),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: { getAssignableUsers: () => Promise.resolve({ data: [] }) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}))

import InstallationDetail from './InstallationDetail'

const rendre = (row) => render(
  <Provider store={configureStore({ reducer: { stock: (s = { produits: [] }) => s } })}>
    <MemoryRouter initialEntries={['/chantiers']}>
      <ThemeProvider>
        <InstallationDetail installation={{ ...row }} onClose={() => {}} onSaved={() => {}} />
      </ThemeProvider>
    </MemoryRouter>
  </Provider>,
)

beforeEach(() => {
  db[1] = { id: 1, reference: 'CH-1', statut: 'materiel_commande', annule: false }
  db[2] = { id: 2, reference: 'CH-2', statut: 'cloture', annule: false }
  db[3] = { id: 3, reference: 'CH-3', statut: 'receptionne', annule: false }
  db[4] = { id: 4, reference: 'CH-4', statut: 'installe', annule: false }
})
afterEach(() => cleanup())

describe('InstallationDetail — ACHT60 dérogations de statut', () => {
  it('acompte non reçu : le motif apparaît et le passage à Planifié aboutit', async () => {
    const user = userEvent.setup()
    rendre(db[1])
    await user.selectOptions(await screen.findByLabelText('Statut'), 'planifie')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    const motif = await screen.findByLabelText(/Motif \(acompte non reçu\)/)
    expect(db[1].statut).toBe('materiel_commande')
    await user.type(motif, 'Virement annoncé')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[1].statut).toBe('planifie'))
  })

  it('clôturé : le motif de réouverture apparaît et l’envoi aboutit', async () => {
    const user = userEvent.setup()
    rendre(db[2])
    await user.selectOptions(await screen.findByLabelText('Statut'), 'receptionne')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    const motif = await screen.findByLabelText(/Motif de réouverture/)
    expect(db[2].statut).toBe('cloture')
    await user.type(motif, 'Réserve oubliée')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[2].statut).toBe('receptionne'))
  })

  it('« Marquer réceptionné » seulement depuis Installé', async () => {
    rendre(db[2])
    await screen.findByLabelText('Statut')
    expect(screen.queryByRole('button', { name: 'Marquer réceptionné' })).toBeNull()
    cleanup()
    rendre(db[3])
    await screen.findByLabelText('Statut')
    expect(screen.queryByRole('button', { name: 'Marquer réceptionné' })).toBeNull()
    cleanup()
    rendre(db[4])
    expect(await screen.findByRole('button', { name: 'Marquer réceptionné' })).toBeInTheDocument()
  })
})
