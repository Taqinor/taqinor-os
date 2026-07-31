import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (mesuré par DataTable/recharts).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WIR123 — `AbonnementMonitoring` (revenu récurrent de supervision) était un
   modèle + ViewSet backend complet (FG244/YSUBS3/YSUBS4) sans aucun
   consommateur frontend. L'écran liste, crée et pilote facturer/suspendre/
   résilier depuis l'UI. */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getAbonnements: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, client_id: 42, installation_id: null, periodicite: 'mensuel', montant: '500.00', statut: 'actif', prochaine_echeance: '2026-08-01' },
      ],
    })),
    createAbonnement: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
    facturerAbonnement: vi.fn(() => Promise.resolve({ data: { facture_id: 9, reference: 'FAC-2026-009', montant_ttc: '600.00' } })),
    suspendreAbonnement: vi.fn(() => Promise.resolve({ data: {} })),
    resilierAbonnement: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [{ id: 42, nom: 'Amrani Solar' }] })),
  },
}))

import monitoringApi from '../../api/monitoringApi'
import AbonnementsPage from './AbonnementsPage'

describe('AbonnementsPage (WIR123 — abonnements de supervision)', () => {
  it('liste les abonnements avec le nom du client', async () => {
    renderPage(<AbonnementsPage />)
    // DataTable rend un tableau bureau ET des cartes mobiles (2 occurrences) :
    // même patron que ParcellesPage.test.jsx (NTAGR4).
    await waitFor(() => expect(screen.getAllByText('Amrani Solar').length).toBeGreaterThan(0))
  })

  it('crée un abonnement depuis le formulaire', async () => {
    const user = userEvent.setup()
    renderPage(<AbonnementsPage />)
    await waitFor(() => expect(screen.getAllByText('Amrani Solar').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvel abonnement/ }))
    await user.click(screen.getByRole('combobox', { name: 'Client' }))
    await user.click(await screen.findByRole('option', { name: 'Amrani Solar' }))
    await user.type(screen.getByLabelText('Montant par période (MAD)'), '500')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(monitoringApi.createAbonnement).toHaveBeenCalledWith(
      expect.objectContaining({ client_id: '42', montant: '500' }),
    ))
  })

  it('facture la période due depuis la ligne', async () => {
    const user = userEvent.setup()
    renderPage(<AbonnementsPage />)
    await waitFor(() => expect(screen.getAllByText('Amrani Solar').length).toBeGreaterThan(0))
    // DataTable rend bureau + mobile (2 boutons identiques pour la même
    // ligne) : les deux appellent la même action, on prend le premier.
    await user.click(screen.getAllByRole('button', { name: 'Facturer la période due' })[0])
    await waitFor(() => expect(monitoringApi.facturerAbonnement).toHaveBeenCalledWith(1))
  })

  it('résilie un abonnement avec un motif', async () => {
    const user = userEvent.setup()
    renderPage(<AbonnementsPage />)
    await waitFor(() => expect(screen.getAllByText('Amrani Solar').length).toBeGreaterThan(0))
    // Idem : bureau + mobile rendent chacun le bouton « Résilier » de ligne.
    await user.click(screen.getAllByRole('button', { name: 'Résilier' })[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Motif de résiliation'), 'Client parti')
    await user.click(within(dialog).getByRole('button', { name: 'Résilier' }))
    await waitFor(() => expect(monitoringApi.resilierAbonnement).toHaveBeenCalledWith(1, 'Client parti'))
  })
})
