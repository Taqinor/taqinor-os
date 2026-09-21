import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor } from '@testing-library/react'

/* CAD143 — onglet EN LECTURE pour la cadence « Générique » (historique,
   encore active sur de vrais leads d'avant le protocole v3, mais qu'aucun
   appelant ne DÉMARRE plus). Aucune écriture depuis cet onglet : pas
   d'Input/Select/Switch, pas de PATCH possible. */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({ data: [] })),
    getCadenceRelance: vi.fn(async (cadence) => ({
      data: cadence === 'generique'
        ? [
          {
            id: 91, cadence: 'generique', ordre: 1, delai_jours: 2,
            delai_minutes: 0, heure_cible: null, canal: 'whatsapp',
            libelle: 'Relance J+2', template_cle: '', actif: true,
          },
          {
            id: 92, cadence: 'generique', ordre: 2, delai_jours: 35,
            delai_minutes: 0, heure_cible: null, canal: 'visite',
            libelle: 'Relance J+35', template_cle: '', actif: true,
          },
        ]
        : [],
    })),
    updateCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import CadenceRelanceEditor from './CadenceRelanceEditor'

beforeEach(() => {
  parametresApi.getCadenceRelance.mockClear()
  parametresApi.updateCadenceRelanceEtape.mockClear()
})
afterEach(() => cleanup())

const renderEditor = async () => {
  await act(async () => {
    render(
      <ThemeProvider>
        <CadenceRelanceEditor />
      </ThemeProvider>,
    )
  })
}

describe('CAD143 onglet Générique en lecture', () => {
  it('affiche un quatrième onglet libellé « historique — ne plus assigner »', async () => {
    await renderEditor()
    expect(screen.getByRole('tab', {
      name: 'Générique — historique, ne plus assigner',
    })).toBeInTheDocument()
    // Les trois onglets existants restent inchangés.
    expect(screen.getByRole('tab', { name: 'Contact' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Après devis' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Réveil' })).toBeInTheDocument()
  })

  it('bascule vers l\'onglet et lit la cadence "generique"', async () => {
    await renderEditor()
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', {
      name: 'Générique — historique, ne plus assigner',
    }))
    await waitFor(() =>
      expect(parametresApi.getCadenceRelance).toHaveBeenCalledWith('generique'))
    expect(await screen.findByText('Relance J+2')).toBeInTheDocument()
    expect(screen.getByText('Relance J+35')).toBeInTheDocument()
  })

  it('ne rend AUCUN contrôle éditable (lecture seule)', async () => {
    await renderEditor()
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', {
      name: 'Générique — historique, ne plus assigner',
    }))
    await screen.findByText('Relance J+2')
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(parametresApi.updateCadenceRelanceEtape).not.toHaveBeenCalled()
  })

  it('n\'affiche jamais de bouton "Active" cliquable — juste un statut texte', async () => {
    await renderEditor()
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', {
      name: 'Générique — historique, ne plus assigner',
    }))
    await screen.findByText('Relance J+2')
    expect(screen.getAllByText('Active')).toHaveLength(2)
  })
})
