import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor } from '@testing-library/react'

/* MRY28 — éditeur des trois cadences de relance (contact / après devis /
   réveil), Paramètres → Référentiels → « Cadences de relance ». Édition en
   place (PATCH) uniquement : aucune création/suppression depuis cet écran
   (les lignes sont posées par `seed_cadence`, MRY4). */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({
      data: [
        { cle: 'identite', label: "Message d'identité" },
        { cle: 'appel_ouverture', label: "Appel d'ouverture" },
      ],
    })),
    getCadenceRelance: vi.fn(async (cadence) => ({
      data: cadence === 'contact'
        ? [
          {
            id: 51, cadence: 'contact', ordre: 1, delai_jours: 0,
            delai_minutes: 0, heure_cible: null, canal: 'whatsapp',
            libelle: "Message d'identité", template_cle: 'identite', actif: true,
          },
          {
            id: 52, cadence: 'contact', ordre: 2, delai_jours: 0,
            delai_minutes: 3, heure_cible: null, canal: 'appel',
            libelle: "Appel d'ouverture", template_cle: 'appel_ouverture', actif: true,
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

describe('MRY28 CadenceRelanceEditor', () => {
  it('charge la cadence « contact » par défaut et affiche ses étapes', async () => {
    await renderEditor()
    await waitFor(() =>
      expect(parametresApi.getCadenceRelance).toHaveBeenCalledWith('contact'))
    expect(await screen.findByDisplayValue("Message d'identité")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Appel d'ouverture")).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
  })

  it('bascule vers l\'onglet « Après devis » sans étape (liste vide)', async () => {
    await renderEditor()
    await screen.findByDisplayValue("Message d'identité")
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: 'Après devis' }))
    await waitFor(() =>
      expect(parametresApi.getCadenceRelance).toHaveBeenCalledWith('apres_devis'))
    expect(await screen.findByText('Aucune étape pour cette cadence.')).toBeInTheDocument()
  })

  it('modifie le délai en minutes et envoie le PATCH attendu', async () => {
    await renderEditor()
    const input = await screen.findByLabelText('Délai (min)', {
      selector: '#cre-min-52',
    })
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.clear(input)
    await user.type(input, '5')
    await user.tab()
    await waitFor(() =>
      expect(parametresApi.updateCadenceRelanceEtape).toHaveBeenCalledWith(
        52, { delai_minutes: 5 }))
  })

  it('bascule l\'interrupteur Actif et envoie le PATCH', async () => {
    await renderEditor()
    await screen.findByDisplayValue("Message d'identité")
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Active — étape 1'))
    await waitFor(() =>
      expect(parametresApi.updateCadenceRelanceEtape).toHaveBeenCalledWith(
        51, { actif: false }))
  })
})
