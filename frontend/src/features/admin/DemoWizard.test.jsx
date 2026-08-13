import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/axios', () => ({ default: apiMock }))

import DemoWizard from './DemoWizard'

afterEach(() => {
  cleanup()
  apiMock.get.mockReset()
  apiMock.post.mockReset()
})

describe('DemoWizard (NTDMO25)', () => {
  it('walks the 3 steps and shows a recap', async () => {
    const user = userEvent.setup()
    render(<DemoWizard />)
    expect(screen.getByText(/Étape 1 \/ 3/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Suivant/i }))
    expect(screen.getByText(/Étape 2 \/ 3/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Suivant/i }))
    expect(screen.getByText(/Étape 3 \/ 3/)).toBeInTheDocument()
    expect(screen.getByText(/Récapitulatif/)).toBeInTheDocument()
  })

  it('triggers generation synchronously and reports done', async () => {
    apiMock.post.mockResolvedValue({
      data: { slug: 'demo-wizard-x', statut: 'termine' },
    })
    const user = userEvent.setup()
    render(<DemoWizard />)
    await user.click(screen.getByRole('button', { name: /Suivant/i }))
    await user.click(screen.getByRole('button', { name: /Suivant/i }))
    await user.click(screen.getByRole('button', { name: /Générer/i }))
    expect(apiMock.post).toHaveBeenCalledWith(
      '/auth/demo-wizard/',
      expect.objectContaining({ profil: 'mixte', densite: 'complet' }),
    )
  })
})
