import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { adminopsApiMock } = vi.hoisted(() => ({
  adminopsApiMock: {
    ciblesImpersonation: vi.fn(),
    demanderImpersonation: vi.fn(),
  },
}))
vi.mock('../../api/adminopsApi', () => ({ default: adminopsApiMock }))

import { MemoryRouter } from 'react-router-dom'
import ImpersonationWizard from './ImpersonationWizard'
import { ThemeProvider } from '../../design/ThemeProvider'

const CIBLES = {
  societes: [
    { id: 1, nom: 'Client Alpha', slug: 'client-alpha' },
    { id: 2, nom: 'Client Beta', slug: 'client-beta' },
  ],
  utilisateurs: [
    { id: 11, username: 'vendeur_alpha', company: 1, societe_nom: 'Client Alpha' },
    { id: 22, username: 'vendeur_beta', company: 2, societe_nom: 'Client Beta' },
  ],
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ImpersonationWizard />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  adminopsApiMock.ciblesImpersonation.mockReset().mockResolvedValue({ data: CIBLES })
  adminopsApiMock.demanderImpersonation.mockReset().mockResolvedValue({ data: {} })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ImpersonationWizard — NTADM32', () => {
  it('affiche le titre et démarre à l\'étape 1 (motif)', async () => {
    renderPage()
    expect(
      screen.getByRole('heading', { name: 'Demander une session support' }),
    ).toBeInTheDocument()
    expect(screen.getByTestId('impersonation-etape-1')).toBeInTheDocument()
    expect(screen.queryByTestId('impersonation-etape-2')).not.toBeInTheDocument()
  })

  it('bloque le passage à l\'étape 2 tant que le motif est vide', async () => {
    renderPage()
    const continuer = screen.getByRole('button', { name: 'Continuer' })
    expect(continuer).toBeDisabled()
    // Un motif composé uniquement d'espaces ne débloque pas non plus.
    await userEvent.type(screen.getByLabelText('Motif de la demande'), '   ')
    expect(screen.getByRole('button', { name: 'Continuer' })).toBeDisabled()
    expect(screen.queryByTestId('impersonation-etape-2')).not.toBeInTheDocument()
  })

  it('passe à l\'étape 2 une fois le motif saisi', async () => {
    renderPage()
    await userEvent.type(
      screen.getByLabelText('Motif de la demande'), 'Diagnostic ticket 4182')
    await userEvent.click(screen.getByRole('button', { name: 'Continuer' }))
    expect(screen.getByTestId('impersonation-etape-2')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByLabelText('Utilisateur à assister')).toBeInTheDocument()
    })
  })

  it('envoie la demande avec le motif et la cible choisie', async () => {
    renderPage()
    await userEvent.type(
      screen.getByLabelText('Motif de la demande'), 'Diagnostic ticket 4182')
    await userEvent.click(screen.getByRole('button', { name: 'Continuer' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Utilisateur à assister')).toBeInTheDocument()
    })
    await userEvent.selectOptions(
      screen.getByLabelText('Utilisateur à assister'), '11')
    await userEvent.click(
      screen.getByRole('button', { name: 'Envoyer la demande' }))

    await waitFor(() => {
      expect(adminopsApiMock.demanderImpersonation).toHaveBeenCalledWith({
        utilisateur_cible: 11,
        motif: 'Diagnostic ticket 4182',
      })
    })
  })

  it('n\'envoie rien si aucune cible n\'est choisie', async () => {
    renderPage()
    await userEvent.type(
      screen.getByLabelText('Motif de la demande'), 'Diagnostic')
    await userEvent.click(screen.getByRole('button', { name: 'Continuer' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Envoyer la demande' }))
    expect(adminopsApiMock.demanderImpersonation).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Choisissez un utilisateur à assister.')
  })

  it('affiche le refus serveur pour un non-support (403)', async () => {
    adminopsApiMock.ciblesImpersonation.mockRejectedValue({
      response: { status: 403 },
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        "Réservé au staff support de l'éditeur.")
    })
  })
})
