import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mocks = vi.hoisted(() => ({ heatmap: vi.fn() }))

vi.mock('../../api/marketingApi', () => ({
  default: { heatmapEngagement: mocks.heatmap },
}))

import HeatmapEnvoi from './HeatmapEnvoi'
import { intensite, libelleMeilleurCreneau } from './heatmapEnvoiLogic'

describe('libelleMeilleurCreneau / intensite (logique pure)', () => {
  it('formule la suggestion en français', () => {
    expect(libelleMeilleurCreneau({ jour: 1, heure: 10, envois: 40, taux_ouverture: 0.42 }))
      .toBe("Vos contacts ouvrent le plus mardi 10h (42 % d'ouverture)")
  })

  it("ne suggère rien sans historique", () => {
    expect(libelleMeilleurCreneau(null)).toBe('')
    expect(libelleMeilleurCreneau({ jour: 0, heure: 9, envois: 0 })).toBe('')
  })

  it('normalise l\'intensité sur le meilleur taux observé', () => {
    expect(intensite({ taux_ouverture: 0.25 }, 0.5)).toBe(0.5)
    expect(intensite({ taux_ouverture: 0.9 }, 0)).toBe(0)
  })
})

describe('HeatmapEnvoi — NTMKT24', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche un état vide propre pour une société sans historique', async () => {
    mocks.heatmap.mockResolvedValue({
      data: { cellules: [], meilleur: null, total_envois: 0 },
    })
    render(<HeatmapEnvoi />)
    await waitFor(() => expect(screen.getByTestId('heatmap-vide')).toBeInTheDocument())
    expect(screen.queryByTestId('heatmap-table')).toBeNull()
  })

  it('peuple la grille depuis l\'historique réel et suggère le meilleur créneau', async () => {
    const meilleur = { jour: 1, heure: 10, envois: 20, ouvertures: 9, taux_ouverture: 0.45 }
    mocks.heatmap.mockResolvedValue({
      data: {
        cellules: [
          { jour: 0, heure: 9, envois: 10, ouvertures: 1, taux_ouverture: 0.1 },
          meilleur,
        ],
        meilleur,
        total_envois: 30,
      },
    })
    render(<HeatmapEnvoi />)
    await waitFor(() => expect(screen.getByTestId('heatmap-table')).toBeInTheDocument())
    expect(screen.getByTestId('heatmap-suggestion'))
      .toHaveTextContent('mardi 10h')
    expect(screen.getByText('45%')).toBeInTheDocument()
    expect(screen.getByText('10%')).toBeInTheDocument()
  })

  it('reste silencieux si le serveur échoue (jamais bloquant)', async () => {
    mocks.heatmap.mockRejectedValue(new Error('boom'))
    render(<HeatmapEnvoi />)
    await waitFor(() => expect(screen.getByTestId('heatmap-vide')).toBeInTheDocument())
  })
})
