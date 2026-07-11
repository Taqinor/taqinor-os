import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const ROWS = [
  {
    id: 1, reference: 'FAC-001', client_id: 42, client_nom: 'ACME SARL',
    client_telephone: '0612345678', montant_du: 1000, niveau: null,
  },
  {
    id: 2, reference: 'FAC-002', client_id: 99, client_nom: 'Globex',
    client_telephone: '0698765432', montant_du: 2000, niveau: null,
  },
]

vi.mock('../../api/ventesApi', () => ({
  default: {
    getRelances: vi.fn(() => Promise.resolve({ data: ROWS })),
    relancerFacture: vi.fn(() => Promise.resolve({ data: {} })),
    whatsappFacture: vi.fn((id) => Promise.resolve({
      data: {
        message: `Message pour facture ${id}`,
        url: `https://ex.example/${id}`,
        wa_url: `https://wa.me/000?text=${id}`,
      },
    })),
  },
}))

import RelancesPage from './RelancesPage'
import ventesApi from '../../api/ventesApi'

/* VX112 — la page /ventes/relances lit ?client=<id> (posé par le drill-down
   de la balance âgée) et pré-filtre la liste sur ce client, sans appel API
   supplémentaire (filtrage d'affichage, miroir du niveauFilter existant). */
describe('RelancesPage (VX112 — pré-filtre client via ?client=)', () => {
  it('sans ?client=, affiche toutes les factures', async () => {
    render(
      <MemoryRouter initialEntries={['/ventes/relances']}>
        <RelancesPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()
    expect(screen.getByText('Globex')).toBeInTheDocument()
  })

  it('avec ?client=42, ne montre que les factures de ce client', async () => {
    render(
      <MemoryRouter initialEntries={['/ventes/relances?client=42']}>
        <RelancesPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()
    expect(screen.queryByText('Globex')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /effacer/ })).toHaveAttribute('href', '/ventes/relances')
  })
})

/* VX116 — la relance en lot propose désormais un DropdownMenu : « Consigner
   uniquement » (comportement inchangé) et « Consigner + aperçu WhatsApp pour
   chacun » (aperçu par client en séquence, jamais d'auto-envoi wa.me). */
describe('RelancesPage (VX116 — relance en lot : consigner + aperçu WhatsApp)', () => {
  beforeEach(() => {
    ventesApi.relancerFacture.mockClear()
    ventesApi.whatsappFacture.mockClear()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(window, 'open').mockImplementation(() => {})
  })

  it('« Consigner uniquement » reste byte-identique : ne consigne que via relancerFacture', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/ventes/relances']}>
        <RelancesPage />
      </MemoryRouter>,
    )
    const row1 = (await screen.findByText('FAC-001')).closest('tr')
    await user.click(within(row1).getByRole('checkbox', { name: /Sélectionner FAC-001/ }))

    await user.click(screen.getByRole('button', { name: /Consigner pour la sélection/ }))
    const menuitem = await screen.findByRole('menuitem', { name: 'Consigner uniquement' })
    await user.click(menuitem)

    await waitFor(() => {
      expect(ventesApi.relancerFacture).toHaveBeenCalledWith('1', { niveau: undefined })
    })
    expect(ventesApi.whatsappFacture).not.toHaveBeenCalled()
    expect(screen.queryByText(/Aperçu du rappel WhatsApp/)).not.toBeInTheDocument()
  })

  it('« Consigner + aperçu WhatsApp pour chacun » consigne tout puis prévisualise en séquence sans auto-envoi', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/ventes/relances']}>
        <RelancesPage />
      </MemoryRouter>,
    )
    const row1 = (await screen.findByText('FAC-001')).closest('tr')
    const row2 = (await screen.findByText('FAC-002')).closest('tr')
    await user.click(within(row1).getByRole('checkbox', { name: /Sélectionner FAC-001/ }))
    await user.click(within(row2).getByRole('checkbox', { name: /Sélectionner FAC-002/ }))

    await user.click(screen.getByRole('button', { name: /Consigner pour la sélection/ }))
    const menuitem = await screen.findByRole('menuitem', { name: /aperçu WhatsApp pour chacun/ })
    await user.click(menuitem)

    // Les deux factures sont consignées (même effet que « Consigner uniquement »).
    await waitFor(() => {
      expect(ventesApi.relancerFacture).toHaveBeenCalledTimes(2)
    })

    // Premier aperçu (FAC-001) : jamais d'ouverture avant clic explicite.
    expect(await screen.findByText('Aperçu du rappel WhatsApp — FAC-001')).toBeInTheDocument()
    expect(window.open).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(window.open).toHaveBeenCalledTimes(1)

    // Enchaîne automatiquement sur le deuxième aperçu (FAC-002).
    expect(await screen.findByText('Aperçu du rappel WhatsApp — FAC-002')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(window.open).toHaveBeenCalledTimes(2)

    // File épuisée : plus de modale.
    await waitFor(() => {
      expect(screen.queryByText(/Aperçu du rappel WhatsApp/)).not.toBeInTheDocument()
    })
  })

  it('annuler un aperçu en file passe quand même au suivant (chacun déjà consigné)', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/ventes/relances']}>
        <RelancesPage />
      </MemoryRouter>,
    )
    const row1 = (await screen.findByText('FAC-001')).closest('tr')
    const row2 = (await screen.findByText('FAC-002')).closest('tr')
    await user.click(within(row1).getByRole('checkbox', { name: /Sélectionner FAC-001/ }))
    await user.click(within(row2).getByRole('checkbox', { name: /Sélectionner FAC-002/ }))
    await user.click(screen.getByRole('button', { name: /Consigner pour la sélection/ }))
    await user.click(await screen.findByRole('menuitem', { name: /aperçu WhatsApp pour chacun/ }))

    expect(await screen.findByText('Aperçu du rappel WhatsApp — FAC-001')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(window.open).not.toHaveBeenCalled()
    expect(await screen.findByText('Aperçu du rappel WhatsApp — FAC-002')).toBeInTheDocument()
  })
})
