import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   CHT22 — Un seul niveau de qualité pour changer le statut.
   ----------------------------------------------------------------------------
   Le Select legacy ±1 (onglet Aperçu, section « Chantier ») ignorait les
   gates CH2 : une transition bloquée finissait en message d'erreur brut au
   save, alors que le stepper CH6 (ChantierGateTimeline, onglet Jalons &
   gates) affiche la liste à puces des raisons (`data-testid=
   "ch6-blocked-reasons"`, déjà couvert par ChantierGateTimeline.test.jsx).
   Ce test verrouille le SECOND chemin : la même 400 `{statut: [...]}`
   (`views/installation.py` -> `TransitionRefusee`) rend désormais le MÊME
   format, jamais un message brut sérialisé.

   Patron établi (WIR243/PaieParametres.test.jsx) : Radix Select ne s'ouvre
   pas de façon fiable sous jsdom (portail + pointer events) — remplacer les
   primitives Select par un <select> natif, le reste de `../../ui` reste réel.
   Le `id` porté par `SelectTrigger` (association label <-> champ, ex.
   "ch-statut") est reporté sur le <select> natif rendu par le mock.
   ========================================================================== */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
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

vi.mock('../../api/gestionProjetApi', () => ({
  default: {
    getChantiers: () => Promise.resolve({ data: { results: [] } }),
    creerProjetDepuisDevis: () => Promise.resolve({ data: { id: 1, code: 'PRJ-0001' } }),
  },
}))

const RAISON = "Le pack de remise client n'est pas complet."

vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
    updateInstallation: vi.fn(() => Promise.reject({
      response: { data: { statut: [RAISON] } },
    })),
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

function makeStore() {
  return configureStore({
    reducer: {
      stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state,
    },
  })
}

function renderDetail(installation) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/chantiers']}>
        <ThemeProvider>
          <InstallationDetail installation={installation} onClose={() => {}} onSaved={() => {}} />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — statut bloqué : raisons visibles (CHT22)', () => {
  it('affiche la liste à puces des raisons (format ch6-blocked-reasons) au lieu d\'un message brut', async () => {
    const user = userEvent.setup()
    renderDetail({
      id: 801, reference: 'CH-CHT22-801', statut: 'signe', annule: false,
    })

    const select = await screen.findByLabelText('Statut')
    await user.selectOptions(select, 'materiel_commande')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))

    const bloc = await screen.findByTestId('ch6-blocked-reasons')
    expect(bloc).toHaveTextContent(RAISON)
    // Jamais le message brut générique EN PLUS du format à puces.
    expect(screen.queryByText('Enregistrement impossible.')).toBeNull()
  })
})
