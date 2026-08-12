import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import ElementsVariablesPaie from './ElementsVariablesPaie.jsx'

/* PACT86 — Éléments variables de paie (bordereau externe). Un bordereau
   exporté doit passer visiblement en statut « exporté » avec sa date SERVEUR,
   sans recalcul des totaux côté client. */

vi.mock('../../api/rhApi', () => ({
  default: {
    getElementsVariablesPaie: vi.fn(() => Promise.resolve({
      data: [{
        id: 3, employe: 9, employe_nom: 'Bennani Youssef', annee: 2026, mois: 7,
        heures_normales: 176, heures_supp: 4, primes: 500, retenues: 100,
        statut: 'valide', statut_display: 'Validé', date_export: null,
      }],
    })),
    getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
    createElementVariablePaie: vi.fn(),
    updateElementVariablePaie: vi.fn(),
    marquerExporteElementVariablePaie: vi.fn(),
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ElementsVariablesPaie />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ElementsVariablesPaie (PACT86)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et propose de marquer exporté une ligne validée', async () => {
    renderScreen()
    expect((await screen.findAllByText('Éléments variables de paie')).length).toBeGreaterThan(0)
    expect((await screen.findAllByRole('button', { name: 'Marquer exporté' }))[0]).toBeInTheDocument()
  })

  it('marque exporté via rhApi.marquerExporteElementVariablePaie et recharge la liste', async () => {
    rhApi.marquerExporteElementVariablePaie.mockResolvedValueOnce({ data: { id: 3, statut: 'exporte' } })
    renderScreen()
    fireEvent.click((await screen.findAllByRole('button', { name: 'Marquer exporté' }))[0])

    await waitFor(() => expect(rhApi.marquerExporteElementVariablePaie).toHaveBeenCalledWith(3))
    // Le rechargement passe par `reloadTick` → l'effet se rejoue APRÈS le
    // retour de l'action : l'attente doit donc porter sur le 2ᵉ appel
    // lui-même, pas s'exécuter juste après le premier `waitFor`.
    await waitFor(() => expect(rhApi.getElementsVariablesPaie).toHaveBeenCalledTimes(2))
  })

  it('crée une ligne via rhApi.createElementVariablePaie', async () => {
    rhApi.createElementVariablePaie.mockResolvedValueOnce({ data: { id: 9 } })
    renderScreen()
    await screen.findAllByText('Éléments variables de paie')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle ligne/ }))[0])
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer' })[0])

    await waitFor(() => expect(rhApi.createElementVariablePaie).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9' }),
    ))
  })
})
