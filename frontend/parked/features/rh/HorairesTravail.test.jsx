import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import HorairesTravail from './HorairesTravail.jsx'

/* PACT89 — Horaires de travail. Une fenêtre Ramadan future doit s'afficher
   « À venir » PUIS « Active » une fois sa date de début atteinte — dérivé de
   la comparaison des dates déjà renvoyées par le serveur, jamais recalculé
   comme une règle métier. */

vi.mock('../../api/rhApi', () => ({
  default: {
    getHorairesTravail: vi.fn(() => Promise.resolve({ data: [] })),
    createHoraireTravail: vi.fn(),
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <HorairesTravail />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('HorairesTravail (PACT89)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche « À venir » pour une fenêtre future puis « Active » une fois commencée', async () => {
    const dansUnMois = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10)
    const hier = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
    const demain = new Date(Date.now() + 86400000).toISOString().slice(0, 10)
    rhApi.getHorairesTravail.mockResolvedValueOnce({
      data: [
        { id: 1, nom: 'Ramadan futur', type_horaire_display: 'Ramadan', heures_semaine: 30, date_debut: dansUnMois, date_fin: null, actif: true },
        { id: 2, nom: 'Ramadan en cours', type_horaire_display: 'Ramadan', heures_semaine: 30, date_debut: hier, date_fin: demain, actif: true },
      ],
    })
    renderScreen()

    expect((await screen.findAllByText('À venir')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Active')).length).toBeGreaterThan(0)
  })

  it('crée un horaire via rhApi.createHoraireTravail', async () => {
    rhApi.createHoraireTravail.mockResolvedValueOnce({ data: { id: 3 } })
    renderScreen()
    await screen.findAllByText('Horaires de travail')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvel horaire/ }))[0])
    fireEvent.change(screen.getByLabelText('Nom'), { target: { value: 'Ramadan 2027' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])

    await waitFor(() => expect(rhApi.createHoraireTravail).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Ramadan 2027', type_horaire: 'standard_44h' }),
    ))
  })
})
