import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// ASAV38 — l'écran n'écrit plus aucune date d'état : seuls les champs édités
// partent, les dates sont celles du serveur (ASAV37) relues après coup.

const serveur = vi.hoisted(() => ({
  claims: [
    { id: 1, equipement_produit: 'Onduleur', equipement_serie: 'SN-1', statut: 'resolu',
      rma_ref: 'OLD', date_signalement: '2026-08-20', date_resolution: '2026-09-01',
      date_envoi_fournisseur: '2026-08-25' },
    { id: 2, equipement_produit: 'Variateur', equipement_serie: 'SN-2', statut: 'ouvert',
      rma_ref: '', date_signalement: '2026-10-01', date_resolution: null,
      date_envoi_fournisseur: null },
  ],
  corps: [],
}))

vi.mock('../../api/savApi', () => ({
  default: {
    getWarrantyClaims: vi.fn(() => Promise.resolve({ data: serveur.claims.map((c) => ({ ...c })) })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    // Serveur d'ASAV37 : les dates du corps sont ignorées ; envoi daté 2026-10-09.
    saveWarrantyClaim: vi.fn((id, payload) => {
      serveur.corps.push(payload)
      const { date_resolution: _a, date_envoi_fournisseur: _b, ...ok } = payload
      const i = serveur.claims.findIndex((c) => c.id === id)
      serveur.claims[i] = { ...serveur.claims[i], ...ok }
      if (ok.statut === 'envoye' && !serveur.claims[i].date_envoi_fournisseur) {
        serveur.claims[i].date_envoi_fournisseur = '2026-10-09'
      }
      return Promise.resolve({ data: serveur.claims[i] })
    }),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getFournisseurs: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import WarrantyClaimsPage from './WarrantyClaimsPage'

afterEach(() => { cleanup(); serveur.corps.length = 0 })

describe('WarrantyClaimsPage — ASAV38 aucune date d\'état écrite par l\'écran', () => {
  it('éditer la réf. RMA ne touche pas « Résolu le » ; passer à « Envoyé » affiche la date serveur', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><ThemeProvider><WarrantyClaimsPage /></ThemeProvider></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText(/Onduleur/).length).toBeGreaterThan(0))

    // Réclamation 1 (résolue le 01/09) : seule la réf. RMA change.
    fireEvent.click(screen.getAllByRole('button', { name: /Éditer/ })[0])
    const champ = screen.getAllByDisplayValue('OLD')[0]
    fireEvent.change(champ, { target: { value: 'NEW' } })
    fireEvent.click(screen.getAllByRole('button', { name: /Enregistrer/ })[0])
    await waitFor(() => expect(serveur.corps).toHaveLength(1))
    expect(serveur.corps[0]).toEqual({ rma_ref: 'NEW' })
    await waitFor(() => expect(screen.getAllByText('01/09/2026').length).toBeGreaterThan(0))

    // Réclamation 2 : passage à « Envoyé » — aucune date dans le corps.
    fireEvent.click(screen.getAllByRole('button', { name: /Éditer/ })[1])
    await user.click(screen.getAllByRole('combobox').find((c) => c.textContent === 'Ouvert'))
    await user.click(await screen.findByRole('option', { name: 'Envoyé au fournisseur' }))
    fireEvent.click(screen.getAllByRole('button', { name: /Enregistrer/ })[0])
    await waitFor(() => expect(serveur.corps).toHaveLength(2))
    expect(serveur.corps[1]).toEqual({ statut: 'envoye' })
    await waitFor(() => expect(screen.getAllByText('09/10/2026').length).toBeGreaterThan(0))
  }, 90000)
})
