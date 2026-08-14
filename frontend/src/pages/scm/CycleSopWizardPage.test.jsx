import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* NTSCM31 — Assistant guidé « Lancer un cycle S&OP ».
   Critère d'acceptation : lancer l'assistant sur une période déjà existante
   affiche une erreur claire au lieu d'un 500. */

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../../api/axios', () => ({ default: apiMock }))

import CycleSopWizardPage from './CycleSopWizardPage.jsx'

afterEach(() => {
  cleanup()
  apiMock.get.mockReset()
  apiMock.post.mockReset()
})

function mount() {
  return render(
    <MemoryRouter initialEntries={['/scm/sop/nouveau']}>
      <CycleSopWizardPage />
    </MemoryRouter>,
  )
}

describe('CycleSopWizardPage (NTSCM31)', () => {
  it('affiche le nombre de produits actifs puis avance les 3 étapes', async () => {
    apiMock.get.mockResolvedValue({ data: { count: 12, results: [] } })
    const user = userEvent.setup()
    mount()

    expect(await screen.findByText(/12 produit\(s\) actif\(s\)/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Suivant/i }))
    expect(await screen.findByText(/Génère \(ou rafraîchit\)/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Passer cette étape/i }))
    expect(await screen.findByText(/Créer le cycle S&OP/)).toBeInTheDocument()
  })

  it('sur une période déjà existante, affiche une erreur claire (jamais un crash)', async () => {
    apiMock.get.mockResolvedValue({ data: { count: 0, results: [] } })
    apiMock.post.mockRejectedValue({
      response: {
        status: 400,
        data: { periode: ['Un cycle S&OP existe déjà pour la période 2026-09.'] },
      },
    })
    const user = userEvent.setup()
    mount()

    await screen.findByText(/produit\(s\) actif\(s\)/)
    await user.click(screen.getByRole('button', { name: /Suivant/i }))
    await user.click(screen.getByRole('button', { name: /Passer cette étape/i }))
    await user.click(screen.getByRole('button', { name: /Créer le cycle/i }))

    expect(await screen.findByText(/existe déjà pour la période/i)).toBeInTheDocument()
  })
})
