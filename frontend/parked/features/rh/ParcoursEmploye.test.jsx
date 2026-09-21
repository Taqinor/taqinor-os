import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import ParcoursEmploye from './ParcoursEmploye.jsx'

/* PACT91 — Parcours (timeline) des employés. Un type ajouté au catalogue doit
   être immédiatement sélectionnable pour une nouvelle ligne, sans
   redéploiement (les deux listes partagent le même état rechargé). */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getTypesLigneParcours: vi.fn(empty),
      getLignesParcours: vi.fn(empty),
      getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
      createTypeLigneParcours: vi.fn(),
      createLigneParcours: vi.fn(),
    },
  }
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ParcoursEmploye />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ParcoursEmploye (PACT91)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module', async () => {
    renderScreen()
    expect((await screen.findAllByText('Parcours des employés')).length).toBeGreaterThan(0)
  })

  it('crée un type puis une ligne de parcours le référençant, sans redéploiement', async () => {
    rhApi.createTypeLigneParcours.mockResolvedValueOnce({ data: { id: 1 } })
    rhApi.getTypesLigneParcours
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [{ id: 1, libelle: 'Expérience', ordre: 0 }] })
    renderScreen()
    await screen.findAllByText('Parcours des employés')

    // « Nouveau type » vit sur la vue « Catalogue de types » : l'écran ouvre
    // par défaut sur « Lignes de parcours ». On bascule d'abord.
    fireEvent.click(screen.getAllByText('Catalogue de types')[0])
    fireEvent.click((await screen.findAllByRole('button', { name: /Nouveau type/ }))[0])
    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'Expérience' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(rhApi.createTypeLigneParcours).toHaveBeenCalledWith(
      expect.objectContaining({ libelle: 'Expérience' }),
    ))

    fireEvent.click(screen.getByRole('radio', { name: 'Lignes de parcours' }))
    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle ligne/ }))[0])
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Type'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Intitulé'), { target: { value: 'Technicien solaire' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])

    await waitFor(() => expect(rhApi.createLigneParcours).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', type: '1', intitule: 'Technicien solaire' }),
    ))
  })
})
