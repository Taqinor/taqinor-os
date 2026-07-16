import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// XMKT34 — le bouton « Générer avec l'IA » est key-gated : sans clé, AUCUNE
// trace UI (la sonde generer-ia-disponible pilote le rendu) ; avec clé, la
// génération remplit objet/corps comme SUGGESTION éditable (jamais envoyée).

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  genererIaDisponible: vi.fn(),
  genererIa: vi.fn(),
}))

vi.mock('../../api/comptaApi', () => ({
  default: {
    campagnes: {
      list: mocks.list,
      create: vi.fn().mockResolvedValue({ data: {} }),
      update: vi.fn().mockResolvedValue({ data: {} }),
      genererIaDisponible: mocks.genererIaDisponible,
      genererIa: mocks.genererIa,
    },
  },
}))

import CampagnesScreen from './CampagnesScreen'

const renderScreen = () => render(
  <MemoryRouter><CampagnesScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [] })
})

describe('CampagnesScreen — gating IA (XMKT34)', () => {
  it("sans clé : aucune trace UI du bouton IA", async () => {
    mocks.genererIaDisponible.mockResolvedValue(
      { data: { configured: false } })
    renderScreen()
    await waitFor(() => expect(mocks.genererIaDisponible).toHaveBeenCalled())
    expect(screen.queryByTestId('campagne-ia-panel')).toBeNull()
    expect(screen.queryByTestId('campagne-ia-generer')).toBeNull()
    expect(screen.queryByText(/Générer avec l'IA/)).toBeNull()
  })

  it("sonde en échec (endpoint absent / 404) : bouton masqué aussi", async () => {
    mocks.genererIaDisponible.mockRejectedValue(new Error('404'))
    renderScreen()
    await waitFor(() => expect(mocks.genererIaDisponible).toHaveBeenCalled())
    expect(screen.queryByTestId('campagne-ia-panel')).toBeNull()
  })

  it('avec clé : la génération remplit objet/corps éditables', async () => {
    mocks.genererIaDisponible.mockResolvedValue(
      { data: { configured: true } })
    mocks.genererIa.mockResolvedValue({ data: {
      ok: true, configured: true,
      objet: 'Offre solaire été', corps: 'Profitez de -20% ce mois-ci.',
    } })
    renderScreen()
    const btn = await screen.findByTestId('campagne-ia-generer')
    fireEvent.click(btn)
    await waitFor(() => expect(mocks.genererIa).toHaveBeenCalled())
    await waitFor(() => {
      expect(screen.getByTestId('campagne-objet').value)
        .toBe('Offre solaire été')
      expect(screen.getByTestId('campagne-corps').value)
        .toBe('Profitez de -20% ce mois-ci.')
    })
    // Les champs restent ÉDITABLES (suggestion, pas verrouillage).
    fireEvent.change(screen.getByTestId('campagne-objet'),
      { target: { value: 'Objet retravaillé' } })
    expect(screen.getByTestId('campagne-objet').value).toBe('Objet retravaillé')
    // Rien n'a été sauvegardé ni envoyé automatiquement.
    expect(mocks.list).toHaveBeenCalledTimes(1)
  })

  it('le canal WhatsApp (XMKT10) est sélectionnable', async () => {
    mocks.genererIaDisponible.mockResolvedValue(
      { data: { configured: false } })
    renderScreen()
    await screen.findByTestId('campagne-canal')
    const select = screen.getByTestId('campagne-canal')
    const options = Array.from(select.querySelectorAll('option'))
      .map(o => o.value)
    expect(options).toContain('whatsapp')
  })
})
