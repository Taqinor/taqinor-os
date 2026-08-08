import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT66 — Avenants de chantier : chiffrage, envoi client (lien public
   tokenisé), suivi de signature. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const {
  avenantsList, avenantsCreate, avenantsFaireApprouver, avenantsApprouver,
} = vi.hoisted(() => ({
  avenantsList: vi.fn(),
  avenantsCreate: vi.fn(() => Promise.resolve({ data: { id: 4 } })),
  avenantsFaireApprouver: vi.fn(() => Promise.resolve({
    data: { avenant: {}, lien_public: '/btp/avenants/public/abc123/' },
  })),
  avenantsApprouver: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    avenants: {
      list: (...args) => avenantsList(...args),
      create: (...args) => avenantsCreate(...args),
      faireApprouver: (...args) => avenantsFaireApprouver(...args),
      approuver: (...args) => avenantsApprouver(...args),
      refuser: vi.fn(() => Promise.resolve({ data: {} })),
    },
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import AvenantsChantier from './AvenantsChantier'

beforeEach(() => {
  vi.clearAllMocks()
  avenantsList.mockResolvedValue({
    data: [
      {
        id: 1, reference: 'AVC-2026-0001', chantier: 5,
        description: 'Renfort charpente', montant_ht: '15000.00', statut: 'brouillon',
      },
    ],
  })
})

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AvenantsChantier (PACT66)', () => {
  it('affiche les avenants existants', async () => {
    withProviders(<AvenantsChantier />)
    await waitFor(() => expect(screen.getAllByText('AVC-2026-0001').length).toBeGreaterThan(0))
    expect(screen.getByText('Renfort charpente')).toBeInTheDocument()
  })

  it('crée un avenant chiffré', async () => {
    const user = userEvent.setup()
    withProviders(<AvenantsChantier />)
    await waitFor(() => expect(screen.getAllByText('AVC-2026-0001').length).toBeGreaterThan(0))

    const chantierOption = await screen.findByRole('option', { name: /Villa Zenith/ })
    await user.selectOptions(screen.getByLabelText("Chantier de l'avenant"), chantierOption)
    await user.type(screen.getByLabelText("Description de l'avenant"), 'Terrassement supplémentaire')
    await user.type(screen.getByLabelText('Montant HT'), '8500')
    await user.click(screen.getByRole('button', { name: "Créer l'avenant" }))

    await waitFor(() => expect(avenantsCreate).toHaveBeenCalledWith(expect.objectContaining({
      chantier: '5', description: 'Terrassement supplémentaire', montant_ht: '8500',
      impact_budget: false,
    })))
  })

  it("envoie l'avenant au client et affiche le lien public d'approbation", async () => {
    const user = userEvent.setup()
    withProviders(<AvenantsChantier />)
    await waitFor(() => expect(screen.getAllByText('AVC-2026-0001').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: 'Détails' }))
    await user.click(screen.getByRole('button', { name: 'Envoyer au client' }))

    await waitFor(() => expect(avenantsFaireApprouver).toHaveBeenCalledWith(1))
    expect(await screen.findByText('/btp/avenants/public/abc123/')).toBeInTheDocument()
  })

  it('approuve un avenant en interne sans passer par le lien public', async () => {
    const user = userEvent.setup()
    withProviders(<AvenantsChantier />)
    await waitFor(() => expect(screen.getAllByText('AVC-2026-0001').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: 'Détails' }))
    await user.click(screen.getByRole('button', { name: 'Approuver en interne' }))

    await waitFor(() => expect(avenantsApprouver).toHaveBeenCalledWith(1))
  })
})
