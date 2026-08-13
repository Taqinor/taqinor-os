import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import JoursBloquesConge from './JoursBloquesConge.jsx'

/* PACT90 — Jours bloqués (congés). Le catalogue des périodes bloquées se
   crée/liste/supprime ici ; le refus de soumission d'une demande de congé qui
   chevauche reste porté par l'écran Congés (contrôle serveur, ?forcer=1). */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getJoursBloquesConge: vi.fn(empty),
      getDepartements: vi.fn(empty),
      createJourBloqueConge: vi.fn(),
      deleteJourBloqueConge: vi.fn(),
    },
  }
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <JoursBloquesConge />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('JoursBloquesConge (PACT90)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module', async () => {
    renderScreen()
    expect((await screen.findAllByText('Jours bloqués (congés)')).length).toBeGreaterThan(0)
  })

  it('crée un blocage via rhApi.createJourBloqueConge', async () => {
    rhApi.createJourBloqueConge.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findAllByText('Jours bloqués (congés)')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouveau blocage/ }))[0])
    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'Haute saison pose' } })
    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-06-01' } })
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-08-31' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])

    await waitFor(() => expect(rhApi.createJourBloqueConge).toHaveBeenCalledWith(
      expect.objectContaining({ libelle: 'Haute saison pose', date_debut: '2026-06-01', date_fin: '2026-08-31' }),
    ))
  })
})
