import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* PVMRQ (fondateur 18/08/2026) — Paramètres → Gammes & marques
   (`ventes.ParametresGammes`, singleton SANS id dans l'URL — le PATCH ne
   prend jamais d'id, contrairement à `AchatsParametresPage`). Écran testé
   AVEC vitest — non exécuté dans cet environnement (junction node_modules
   vide) ; écrit pour suivre exactement le patron d'AchatsParametresPage.test.jsx. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getParametresGammes: vi.fn(() => Promise.resolve({
      data: {
        id: 3,
        deux_gammes: false,
        nom_essentielle: 'Essentielle',
        nom_premium: 'Premium',
        marques: {
          Essentielle: { panneau: 'Jinko' },
          Premium: {},
        },
      },
    })),
    updateParametresGammes: vi.fn((data) => Promise.resolve({
      data: { id: 3, ...data },
    })),
  },
}))

import ventesApi from '../../api/ventesApi'
import GammesMarquesPage from './GammesMarquesPage'

describe('GammesMarquesPage (PVMRQ — Paramètres → Gammes & marques)', () => {
  it('charge le réglage existant : une seule colonne (Essentielle) visible quand deux_gammes est faux', async () => {
    renderPage(<GammesMarquesPage />)

    expect(await screen.findByText('Gammes & marques')).toBeInTheDocument()
    await waitFor(() => expect(ventesApi.getParametresGammes).toHaveBeenCalled())
    expect(screen.getByRole('switch', { name: /deux gammes/i })).not.toBeChecked()
    expect(screen.getByLabelText(/Marque Essentielle — Panneaux/i)).toHaveValue('Jinko')
    // Colonne Premium absente tant que deux_gammes est désactivé.
    expect(screen.queryByLabelText(/Marque Premium — Panneaux/i)).not.toBeInTheDocument()
  })

  it('activer « deux gammes » fait apparaître la colonne Premium', async () => {
    renderPage(<GammesMarquesPage />)
    await screen.findByText('Gammes & marques')

    const toggle = await screen.findByRole('switch', { name: /deux gammes/i })
    await userEvent.click(toggle)

    expect(await screen.findByLabelText(/Marque Premium — Panneaux/i)).toBeInTheDocument()
  })

  it('saisir une marque pour un rôle puis Enregistrer envoie le PATCH avec la bonne forme (slots fixes)', async () => {
    renderPage(<GammesMarquesPage />)
    await screen.findByText('Gammes & marques')

    const onduleurInput = await screen.findByLabelText(/Marque Essentielle — Onduleur Injection/i)
    await userEvent.type(onduleurInput, 'Huawei')
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))

    await waitFor(() => expect(ventesApi.updateParametresGammes).toHaveBeenCalledWith(
      expect.objectContaining({
        deux_gammes: false,
        marques: expect.objectContaining({
          Essentielle: expect.objectContaining({
            panneau: 'Jinko', onduleur_reseau: 'Huawei',
          }),
        }),
      }),
    ))
  })

  it('renommer le libellé Premium met à jour l\'en-tête de colonne (une fois deux gammes activé)', async () => {
    renderPage(<GammesMarquesPage />)
    await screen.findByText('Gammes & marques')

    await userEvent.click(await screen.findByRole('switch', { name: /deux gammes/i }))
    const nomPremiumInput = await screen.findByLabelText(/Libellé de la gamme Premium/i)
    await userEvent.clear(nomPremiumInput)
    await userEvent.type(nomPremiumInput, 'Luxe')

    expect(await screen.findByLabelText(/Marque Luxe — Panneaux/i)).toBeInTheDocument()
  })

  it('champ vide = aucune préférence : la valeur envoyée reste une chaîne vide, jamais omise silencieusement', async () => {
    renderPage(<GammesMarquesPage />)
    await screen.findByText('Gammes & marques')

    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))

    await waitFor(() => expect(ventesApi.updateParametresGammes).toHaveBeenCalledWith(
      expect.objectContaining({
        marques: expect.objectContaining({
          Essentielle: expect.objectContaining({ panneau: 'Jinko' }),
        }),
      }),
    ))
  })
})
