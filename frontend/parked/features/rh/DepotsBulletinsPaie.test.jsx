import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import DepotsBulletinsPaie from './DepotsBulletinsPaie.jsx'

/* PACT82 — Dépôt des bulletins de paie (FG196). Un dépôt réussi doit
   apparaître immédiatement dans la liste rechargée, sans filtrage côté
   client d'une donnée déjà scopée société par le serveur. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getBulletinsPaie: vi.fn(empty),
      getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
      uploadBulletinPaie: vi.fn(),
    },
  }
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <DepotsBulletinsPaie />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('DepotsBulletinsPaie (PACT82)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module', async () => {
    renderScreen()
    expect((await screen.findAllByText('Bulletins de paie')).length).toBeGreaterThan(0)
  })

  it('dépose un bulletin via rhApi.uploadBulletinPaie et recharge la liste', async () => {
    rhApi.uploadBulletinPaie.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findAllByText('Bulletins de paie')

    fireEvent.click((await screen.findAllByRole('button', { name: /Déposer un bulletin/ }))[0])
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })

    const file = new File(['contenu'], 'bulletin.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]')
    await userEvent.upload(input, file)

    fireEvent.click(screen.getAllByRole('button', { name: 'Déposer' })[0])

    await waitFor(() => expect(rhApi.uploadBulletinPaie).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9' }),
    ))
    expect(rhApi.getBulletinsPaie).toHaveBeenCalledTimes(2)
  })
})
