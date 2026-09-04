import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { toast } from '../../../ui'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* PACT33 — Consolidation groupe (NTFIN1-9). Un cycle VERROUILLÉ refuse toute
   modification de collecte (400 serveur) — l'écran doit afficher ce refus TEL
   QUEL, jamais planter (Done= de PACT33). EntiteConsolidation reste HORS
   PÉRIMÈTRE (mécanisme séparé, non fondu ici). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  cycles: vi.fn(),
  collecter: vi.fn(),
  exercices: vi.fn(),
  // AUDV05 — conversion d'une liasse en devise de présentation (NTFIN5).
  convertirEntite: vi.fn(),
  liasses: vi.fn().mockResolvedValue({ data: [] }),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    cyclesConsolidation: {
      list: mocks.cycles,
      collecter: mocks.collecter,
      convertirEntite: mocks.convertirEntite,
    },
    liassesRemontee: { list: mocks.liasses },
    mappingsConsolidation: { list: vi.fn().mockResolvedValue({ data: [] }) },
    operationsInterco: { list: vi.fn().mockResolvedValue({ data: [] }) },
    margesInternesStock: { list: vi.fn().mockResolvedValue({ data: [] }) },
    eliminationsTitres: { list: vi.fn().mockResolvedValue({ data: [] }) },
    exercices: { list: mocks.exercices },
    comptes: { list: vi.fn().mockResolvedValue({ data: [] }) },
  },
}))

import ConsolidationGroupePage from './ConsolidationGroupePage.jsx'

function mount({ route = '/' } = {}) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <ThemeProvider><ConsolidationGroupePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ConsolidationGroupePage — cycle verrouillé (PACT33)', () => {
  it('affiche le refus serveur tel quel au lieu de planter', async () => {
    mocks.exercices.mockResolvedValue({ data: [] })
    mocks.cycles.mockResolvedValue({
      data: [{ id: 4, libelle: 'Consolidation 2026', exercice: 1,
        date_debut: '2026-01-01', date_fin: '2026-12-31',
        devise_presentation: 'MAD', statut: 'valide', statut_display: 'Validé',
        verrouille: true, tolerance_interco: '0.00' }],
    })
    mocks.collecter.mockRejectedValueOnce({
      response: { data: { detail: 'Cycle verrouillé : la collecte est refusée.' } },
    })
    const erreur = vi.spyOn(toast, 'error')
    mount()

    expect((await screen.findAllByText('Consolidation 2026')).length).toBeGreaterThan(0)
    const bouton = screen.getAllByRole('button', { name: /Collecter les liasses/i })[0]
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.collecter).toHaveBeenCalledWith(4, {}))
    // Le refus serveur part au TOAST (aucun `Toaster` monté dans ce rendu) :
    // on espionne l'appel, ce qui prouve exactement ce qui compte — le
    // message du serveur est relayé TEL QUEL, jamais remplacé par un texte
    // générique.
    expect(erreur).toHaveBeenCalledWith('Cycle verrouillé : la collecte est refusée.')
    // Un cycle verrouillé propose « Ouvrir » (rouvrir), jamais « Verrouiller ».
    // `RowActions` ne révèle que les 2 PREMIÈRES actions en raccourci (ici
    // Collecter + Exporter la liasse) : les autres vivent dans le menu kebab,
    // toujours monté. On l'ouvre pour lire la liste réelle des actions.
    const ligne = (await screen.findAllByText('Consolidation 2026'))
      .map((el) => el.closest('tr')).find(Boolean)
    await userEvent.click(within(ligne).getByLabelText("Plus d'actions sur la ligne"))
    expect(await screen.findByRole('menuitem', { name: /Ouvrir \(déverrouiller\)/i }))
      .toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Verrouiller' })).toBeNull()
  })
})

/* AUDV05 / NTFIN5 (DRAFT165-50) — `services.convertir_entite` n'avait aucun
   appelant : un groupe avec une filiale en devise étrangère ne pouvait PAS
   consolider depuis l'écran. La charge utile vient de l'exemple COMMITTÉ
   (`apps/compta/contract_samples/consolidation_conversion_entite.json`), le
   même que le test backend affirme contre la vraie réponse de la vue. */
describe('ConsolidationGroupePage — conversion de devise (AUDV05)', () => {
  it('convertit une liasse et AFFICHE l’écart de conversion du serveur', async () => {
    const conversion = exempleContrat('compta', 'consolidation_conversion_entite')
    mocks.exercices.mockResolvedValue({ data: [] })
    mocks.cycles.mockResolvedValue({ data: [] })
    mocks.liasses.mockResolvedValue({
      data: [{ id: conversion.liasse, cycle: 4, entite: 9,
        devise_locale: 'EUR', statut: 'collecte',
        statut_display: 'Collectée', date_collecte: '2026-08-31' }],
    })
    mocks.convertirEntite.mockResolvedValue({ data: conversion })

    mount({ route: '/?onglet=liasses' })

    const ligne = (await screen.findAllByText('EUR'))
      .map((el) => el.closest('tr')).find(Boolean)
    await userEvent.click(
      within(ligne).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByRole(
      'menuitem', { name: /Convertir en devise de présentation/i }))

    fireEvent.change(screen.getByLabelText(/Cours de clôture/), {
      target: { value: '10' },
    })
    fireEvent.change(screen.getByLabelText(/Cours moyen/), {
      target: { value: '11' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Convertir' }))

    await waitFor(() => {
      expect(mocks.convertirEntite).toHaveBeenCalledWith(4, {
        liasse: conversion.liasse, taux_cloture: '10', taux_moyen: '11',
      })
    })
    await waitFor(() => {
      expect(screen.getByText('Écart de conversion (CTA)')).toBeInTheDocument()
    })
    // Le compte converti est rendu tel que le serveur l'a calculé.
    expect(screen.getByText(conversion.lignes[0].numero)).toBeInTheDocument()
  })
})
