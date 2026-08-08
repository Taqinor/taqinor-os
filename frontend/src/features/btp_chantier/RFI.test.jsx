import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT63 — RFI : question numérotée par chantier, délai en jours ouvrés
   converti en date limite CÔTÉ SERVEUR, alerte de retard, fil de réponses,
   clôture. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { rfiList, rfiCreate, rfiRepondre, rfiClore } = vi.hoisted(() => ({
  rfiList: vi.fn(),
  rfiCreate: vi.fn(() => Promise.resolve({ data: { id: 10 } })),
  rfiRepondre: vi.fn(() => Promise.resolve({ data: {} })),
  rfiClore: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    rfi: {
      list: (...args) => rfiList(...args),
      create: (...args) => rfiCreate(...args),
      repondre: (...args) => rfiRepondre(...args),
      clore: (...args) => rfiClore(...args),
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

import RFI from './RFI'

beforeEach(() => {
  vi.clearAllMocks()
  rfiList.mockResolvedValue({
    data: [
      {
        id: 1, numero: 1, chantier: 5, question: 'Quelle section de câble ?',
        destinataire_texte: 'BET Électricité', date_limite_reponse: '2026-01-01',
        statut: 'ouvert', en_retard: true, reponses: [],
      },
      {
        id: 2, numero: 2, chantier: 5, question: 'Confirmer la teinte de peinture',
        destinataire_texte: 'MOE', date_limite_reponse: '2099-01-01',
        statut: 'repondu', en_retard: false,
        reponses: [{ id: 20, texte: 'RAL 9010', auteur: null, date_creation: '2026-01-01' }],
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

describe('RFI (PACT63)', () => {
  it('affiche la liste des RFI avec l’alerte de retard', async () => {
    withProviders(<RFI />)
    await waitFor(() => expect(screen.getAllByText('Quelle section de câble ?').length).toBeGreaterThan(0))
    expect(screen.getByText('En retard')).toBeInTheDocument()
    expect(screen.getByText('Confirmer la teinte de peinture')).toBeInTheDocument()
  })

  it('affiche le fil de réponses d’un RFI déjà répondu', async () => {
    const user = userEvent.setup()
    withProviders(<RFI />)
    await waitFor(() => expect(screen.getAllByText('Confirmer la teinte de peinture').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[1])
    expect(await screen.findByText('RAL 9010')).toBeInTheDocument()
  })

  it('pose une nouvelle question avec un délai en jours ouvrés', async () => {
    const user = userEvent.setup()
    withProviders(<RFI />)
    await waitFor(() => expect(screen.getAllByText('Quelle section de câble ?').length).toBeGreaterThan(0))

    const chantierOption = await screen.findByRole('option', { name: /Villa Zenith/ })
    await user.selectOptions(screen.getByLabelText('Chantier de la demande'), chantierOption)
    await user.type(screen.getByLabelText('Question'), 'Type de fixation toiture ?')
    await user.clear(screen.getByLabelText('Délai en jours ouvrés'))
    await user.type(screen.getByLabelText('Délai en jours ouvrés'), '3')
    await user.click(screen.getByRole('button', { name: 'Poser la question' }))

    await waitFor(() => expect(rfiCreate).toHaveBeenCalledWith(expect.objectContaining({
      chantier: '5', question: 'Type de fixation toiture ?', delai_jours: 3,
    })))
  })

  it('répond à un RFI ouvert puis peut le clore', async () => {
    const user = userEvent.setup()
    withProviders(<RFI />)
    await waitFor(() => expect(screen.getAllByText('Quelle section de câble ?').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await user.type(screen.getByLabelText('Texte de la réponse'), 'Section 2.5 mm²')
    await user.click(screen.getByRole('button', { name: 'Répondre' }))
    await waitFor(() => expect(rfiRepondre).toHaveBeenCalledWith(1, 'Section 2.5 mm²'))

    await user.click(screen.getByRole('button', { name: 'Clore' }))
    await waitFor(() => expect(rfiClore).toHaveBeenCalledWith(1))
  })
})
