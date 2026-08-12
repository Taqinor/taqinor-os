import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import GrillesSalariales from './GrillesSalariales.jsx'

/* PACT88 — Grilles salariales (SENSIBLE, salaires_voir). Un compte sans cette
   permission doit voir le 403 SERVEUR affiché tel quel — jamais un masquage
   côté client d'une donnée que le serveur a refusée. */

vi.mock('../../api/rhApi', () => ({
  default: {
    getGrillesSalariales: vi.fn(),
    getPostes: vi.fn(() => Promise.resolve({ data: [{ id: 2, intitule: 'Technicien' }] })),
    createGrilleSalariale: vi.fn(),
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <GrillesSalariales />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('GrillesSalariales (PACT88)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module quand le chargement réussit', async () => {
    rhApi.getGrillesSalariales.mockResolvedValueOnce({
      data: [{ id: 1, poste: 2, salaire_min: 4000, salaire_max: 6000, date_effet: '2026-01-01' }],
    })
    renderScreen()
    expect((await screen.findAllByText('Grilles salariales')).length).toBeGreaterThan(0)
  })

  it('relaie le 403 serveur (salaires_voir manquant) tel quel', async () => {
    rhApi.getGrillesSalariales.mockRejectedValueOnce({
      response: { status: 403, data: { detail: "Vous n'avez pas la permission d'effectuer cette action." } },
    })
    renderScreen()
    expect((await screen.findAllByText("Vous n'avez pas la permission d'effectuer cette action.")).length).toBeGreaterThan(0)
  })

  it('crée une bande salariale via rhApi.createGrilleSalariale', async () => {
    rhApi.getGrillesSalariales.mockResolvedValueOnce({ data: [] })
    rhApi.createGrilleSalariale.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findAllByText('Grilles salariales')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle bande/ }))[0])
    fireEvent.change(screen.getByLabelText('Poste'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Salaire minimum (MAD)'), { target: { value: '4000' } })
    fireEvent.change(screen.getByLabelText('Salaire maximum (MAD)'), { target: { value: '6000' } })
    fireEvent.change(screen.getByLabelText('Date d’effet'), { target: { value: '2026-01-01' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])

    await waitFor(() => expect(rhApi.createGrilleSalariale).toHaveBeenCalledWith(
      expect.objectContaining({ poste: '2', salaire_min: '4000', salaire_max: '6000' }),
    ))
  })
})
