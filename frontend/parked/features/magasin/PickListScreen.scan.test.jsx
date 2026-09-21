import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* WIR193 — le panneau scan-first XSTK5 (`PickingScanPanel`) était construit et
   testé mais monté NULLE PART. Ce test garantit qu'il est ATTEIGNABLE depuis
   l'écran routé `/magasin/prelevements` : ouvrir un bon → onglet « Scan ». */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const PICK_LIST = {
  id: 7,
  reference: 'PICK-202607-0003',
  statut: 'en_cours',
  date_creation: '2026-07-03',
  installation_nom: 'Chantier Bouskoura',
  lignes: [
    {
      id: 21, produit: 5, produit_nom: 'Onduleur 5kW', bin_code: 'A-01-01',
      quantite_demandee: 2, quantite_prelevee: 0, preleve: false, ordre: 1,
    },
  ],
}

vi.mock('../../api/stockApi', () => ({
  default: { resolveCode: vi.fn() },
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getPickLists: vi.fn(() => Promise.resolve({ data: [PICK_LIST] })),
    getPickList: vi.fn(() => Promise.resolve({ data: PICK_LIST })),
    updatePickListLigne: vi.fn(() => Promise.resolve({ data: PICK_LIST.lignes[0] })),
    demarrerPickList: vi.fn(() => Promise.resolve({ data: PICK_LIST })),
    terminerPickList: vi.fn(() => Promise.resolve({ data: PICK_LIST })),
  },
}))

import installationsApi from '../../api/installationsApi'
import PickListScreen from './PickListScreen'
// ListShell passe par le moteur `ui/datatable` (useDensity) : il EXIGE un
// <ThemeProvider> (présent en prod via <Layout>). Harnais uniquement.
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeEach(() => { vi.clearAllMocks() })

describe('PickListScreen — WIR193 onglet Scan', () => {
  it('monte PickingScanPanel quand on bascule sur « Scan »', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <MemoryRouter initialEntries={['/magasin/prelevements']}>
        <ThemeProvider><PickListScreen /></ThemeProvider>
      </MemoryRouter>,
    )

    // Ouvre le bon (clic sur sa ligne). Le moteur DataTable rend la table ET
    // le repli en cartes : on porte la requête sur la TABLE seule.
    await waitFor(() => expect(container.querySelector('[data-dt-table]')).not.toBeNull())
    const table = within(container.querySelector('[data-dt-table]'))
    await user.click(await table.findByText('PICK-202607-0003'))
    await waitFor(() => expect(installationsApi.getPickList).toHaveBeenCalledWith(7))

    // L'onglet existe et n'est PAS actif par défaut (la liste reste le geste
    // historique) : aucune barre de scan tant qu'on ne bascule pas.
    expect(screen.queryByLabelText('Code scanné ou saisi manuellement')).toBeNull()

    await user.click(screen.getByRole('radio', { name: 'Scan' }))

    // Le panneau scan-first est monté : sa barre de saisie est là.
    expect(
      await screen.findByLabelText('Code scanné ou saisi manuellement'),
    ).toBeInTheDocument()
  })
})
