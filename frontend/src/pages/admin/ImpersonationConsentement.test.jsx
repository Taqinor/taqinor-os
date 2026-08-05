import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { adminopsApiMock } = vi.hoisted(() => ({
  adminopsApiMock: {
    impersonationsEnAttente: vi.fn(),
    consentirImpersonation: vi.fn(),
    refuserImpersonation: vi.fn(),
    terminerImpersonation: vi.fn(),
  },
}))
vi.mock('../../api/adminopsApi', () => ({ default: adminopsApiMock }))

import { MemoryRouter } from 'react-router-dom'
import ImpersonationConsentement from './ImpersonationConsentement'
import { ThemeProvider } from '../../design/ThemeProvider'

const EN_ATTENTE = [{
  id: 7,
  cible_nom: 'vendeur_alpha',
  support_nom: 'support_editeur',
  motif: 'Diagnostic ticket 4182',
  statut: 'en_attente',
  consentement_donne: false,
}]

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ImpersonationConsentement />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  adminopsApiMock.impersonationsEnAttente.mockReset()
    .mockResolvedValue({ data: EN_ATTENTE })
  adminopsApiMock.consentirImpersonation.mockReset().mockResolvedValue({ data: {} })
  adminopsApiMock.refuserImpersonation.mockReset().mockResolvedValue({ data: {} })
  adminopsApiMock.terminerImpersonation.mockReset().mockResolvedValue({ data: {} })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ImpersonationConsentement — NTADM22', () => {
  it('liste la demande en attente avec son motif', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('impersonation-consentement-table'))
        .toBeInTheDocument()
    })
    expect(screen.getByText('Diagnostic ticket 4182')).toBeInTheDocument()
    expect(screen.getByText('En attente de votre décision')).toBeInTheDocument()
  })

  it('autorise la demande au clic sur « Autoriser »', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('button',
        { name: 'Autoriser la demande pour vendeur_alpha' })).toBeInTheDocument()
    })
    await userEvent.click(screen.getByRole('button',
      { name: 'Autoriser la demande pour vendeur_alpha' }))
    await waitFor(() => {
      expect(adminopsApiMock.consentirImpersonation).toHaveBeenCalledWith(7)
    })
  })

  it('refuse la demande au clic sur « Refuser »', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('button',
        { name: 'Refuser la demande pour vendeur_alpha' })).toBeInTheDocument()
    })
    await userEvent.click(screen.getByRole('button',
      { name: 'Refuser la demande pour vendeur_alpha' }))
    await waitFor(() => {
      expect(adminopsApiMock.refuserImpersonation).toHaveBeenCalledWith(7)
    })
  })

  it('n\'offre aucune décision pour une demande expirée', async () => {
    adminopsApiMock.impersonationsEnAttente.mockResolvedValue({
      data: [{ ...EN_ATTENTE[0], statut: 'expiree' }],
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Expirée')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button',
      { name: 'Autoriser la demande pour vendeur_alpha' })).not.toBeInTheDocument()
  })

  it('affiche un état vide quand il n\'y a aucune demande', async () => {
    adminopsApiMock.impersonationsEnAttente.mockResolvedValue({ data: [] })
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('impersonation-aucune')).toBeInTheDocument()
    })
  })
})
