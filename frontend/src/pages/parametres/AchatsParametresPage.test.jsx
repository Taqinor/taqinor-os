import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WIR26 — Paramètres → Achats (`stock.AchatsParametres`, singleton par
   société). Le PATCH exige un `id` (route détail du ViewSet) : obtenu via le
   GET précédent, jamais deviné côté client. */

vi.mock('../../api/stockApi', () => ({
  default: {
    getAchatsParametres: vi.fn(() => Promise.resolve({
      data: {
        id: 9,
        bloquer_paiement_conformite_expiree: false,
        ras_tva_actif: false,
        tolerance_prix_pct: '0.00',
        tolerance_prix_absolu_mad: '0.00',
        tolerance_quantite_pct: '0.00',
      },
    })),
    updateAchatsParametres: vi.fn((id, data) => Promise.resolve({
      data: {
        id,
        bloquer_paiement_conformite_expiree: false,
        ras_tva_actif: false,
        tolerance_prix_pct: '0.00',
        tolerance_prix_absolu_mad: '0.00',
        tolerance_quantite_pct: '0.00',
        ...data,
      },
    })),
  },
}))

import stockApi from '../../api/stockApi'
import AchatsParametresPage from './AchatsParametresPage'

describe('AchatsParametresPage (WIR26 — Paramètres → Achats)', () => {
  it('charge le réglage existant', async () => {
    renderPage(<AchatsParametresPage />)

    expect(await screen.findByText('Achats')).toBeInTheDocument()
    await waitFor(() => expect(stockApi.getAchatsParametres).toHaveBeenCalled())
    expect(screen.getByRole('switch', { name: /RAS-TVA/i })).not.toBeChecked()
  })

  it('basculer RAS-TVA puis enregistrer envoie le PATCH sur l\'id du GET', async () => {
    renderPage(<AchatsParametresPage />)
    await screen.findByText('Achats')

    const rasTvaSwitch = await screen.findByRole('switch', { name: /RAS-TVA/i })
    await userEvent.click(rasTvaSwitch)
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))

    await waitFor(() => expect(stockApi.updateAchatsParametres).toHaveBeenCalledWith(
      9, expect.objectContaining({ ras_tva_actif: true }),
    ))
  })

  it('modifier une tolérance XPUR10 puis enregistrer envoie la nouvelle valeur', async () => {
    renderPage(<AchatsParametresPage />)
    await screen.findByText('Achats')

    const tolInput = await screen.findByLabelText(/Écart de prix toléré \(%\)/i)
    await userEvent.clear(tolInput)
    await userEvent.type(tolInput, '5')
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))

    await waitFor(() => expect(stockApi.updateAchatsParametres).toHaveBeenCalledWith(
      9, expect.objectContaining({ tolerance_prix_pct: '5' }),
    ))
  })

  it('n\'affiche jamais un état bloqué : le bouton Enregistrer se désactive uniquement sans id', async () => {
    stockApi.getAchatsParametres.mockImplementationOnce(() => Promise.reject({ response: { status: 500 } }))
    renderPage(<AchatsParametresPage />)

    await screen.findByText('Achats')
    expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeDisabled()
  })
})
