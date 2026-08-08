import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import EntretiensSortie from './EntretiensSortie.jsx'

/* PACT87 — Entretiens de sortie. Un second entretien pour le même employé
   doit être refusé avec le message d'erreur SERVEUR (contrainte d'unicité),
   jamais par une validation front. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getEntretiensSortie: vi.fn(empty),
      getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
      createEntretienSortie: vi.fn(),
    },
  }
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <EntretiensSortie />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('EntretiensSortie (PACT87)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module', async () => {
    renderScreen()
    expect(await screen.findByText('Entretiens de sortie')).toBeInTheDocument()
  })

  it('crée un entretien via rhApi.createEntretienSortie', async () => {
    rhApi.createEntretienSortie.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findByText('Entretiens de sortie')

    fireEvent.click(await screen.findByRole('button', { name: /Nouvel entretien/ }))
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(rhApi.createEntretienSortie).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9' }),
    ))
  })

  it('affiche le refus serveur (contrainte d’unicité) tel quel, sans validation front', async () => {
    rhApi.createEntretienSortie.mockRejectedValueOnce({
      response: { data: { employe: ['Entretien de sortie avec ce Employé existe déjà.'] } },
    })
    renderScreen()
    await screen.findByText('Entretiens de sortie')

    fireEvent.click(await screen.findByRole('button', { name: /Nouvel entretien/ }))
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText('Entretien de sortie avec ce Employé existe déjà.')).toBeInTheDocument()
  })
})
