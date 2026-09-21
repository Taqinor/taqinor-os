import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR76 — les `create*` de contratsApi (createRetenue/createCaution/
   createEcheancier) n'avaient aucun appelant sur FinancesPage.jsx : seules des
   actions ponctuelles (libérer/pointer/marquer fournie) existaient. Ce test
   prouve que les trois formulaires de création sont bien câblés. */

const { createRetenue, createCaution, createEcheancier } = vi.hoisted(() => ({
  createRetenue: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  createCaution: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  createEcheancier: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/contratsApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getRetenues: empty,
      getCautions: empty,
      getEcheanciers: empty,
      getLignesEcheance: empty,
      getIndexations: empty,
      getPiecesConformite: empty,
      getContrats: () => Promise.resolve({
        data: [{ id: 3, reference: 'CT-2026-07-0003', objet: 'Maintenance PV' }],
      }),
      createRetenue,
      createCaution,
      createEcheancier,
      libererRetenue: () => Promise.resolve({ data: {} }),
      pointerPaiement: () => Promise.resolve({ data: {} }),
      marquerPieceFournie: () => Promise.resolve({ data: {} }),
    },
  }
})

import FinancesPage from './FinancesPage'

function renderPage() {
  return render(<ThemeProvider><FinancesPage /></ThemeProvider>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('FinancesPage — WIR76 formulaires de création', () => {
  it('crée une retenue de garantie depuis l’onglet Retenues', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Retenues (0)')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Nouvelle retenue' }))
    await userEvent.click(screen.getByRole('combobox', { name: 'Contrat' }))
    await userEvent.click(await screen.findByRole('option', { name: /CT-2026-07-0003/ }))
    fireEvent.change(screen.getByLabelText('Montant de base'), { target: { value: '10000' } })
    fireEvent.change(screen.getByLabelText('Taux de retenue (%)'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createRetenue).toHaveBeenCalledWith(expect.objectContaining({
      contrat: '3', montant_base: '10000', taux: '5',
    })))
  })

  it('crée une caution depuis l’onglet Cautions', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Retenues (0)')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Cautions/ }))

    fireEvent.click(await screen.findByRole('button', { name: 'Nouvelle caution' }))
    await userEvent.click(screen.getByRole('combobox', { name: 'Contrat' }))
    await userEvent.click(await screen.findByRole('option', { name: /CT-2026-07-0003/ }))
    fireEvent.change(screen.getByLabelText('Montant'), { target: { value: '50000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createCaution).toHaveBeenCalledWith(expect.objectContaining({
      contrat: '3', type_caution: 'bonne_execution', montant: '50000',
    })))
  })

  it('crée un échéancier depuis l’onglet Échéanciers', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Retenues (0)')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /Échéanciers/ }))

    fireEvent.click(await screen.findByRole('button', { name: 'Nouvel échéancier' }))
    fireEvent.change(await screen.findByLabelText('Libellé'), { target: { value: 'Paiement chantier' } })
    await userEvent.click(screen.getByRole('combobox', { name: 'Contrat' }))
    await userEvent.click(await screen.findByRole('option', { name: /CT-2026-07-0003/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createEcheancier).toHaveBeenCalledWith(expect.objectContaining({
      contrat: '3', libelle: 'Paiement chantier', periodicite: 'mensuelle',
    })))
  })
})
