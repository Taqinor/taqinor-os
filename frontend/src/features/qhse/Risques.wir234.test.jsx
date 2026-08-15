import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR234 — les exercices d'urgence (drills) n'étaient ni planifiables ni
   avançables depuis l'écran (registre lecture seule). On vérifie planifier
   (création), réaliser (planifie → realise) et créer une CAPA d'écart. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const { empty, exerciceCreate, exerciceRealiser, exerciceCreerCapa } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  exerciceCreate: vi.fn(() => Promise.resolve({ data: { id: 61 } })),
  exerciceRealiser: vi.fn(() => Promise.resolve({ data: {} })),
  exerciceCreerCapa: vi.fn(() => Promise.resolve({ data: { id: 70 } })),
}))

const EXERCICE_PLANIFIE = {
  id: 61, plan_titre: 'Évacuation atelier', type_exercice: 'evacuation',
  date_prevue: '2026-09-01', date_realisee: null, statut: 'planifie',
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    evaluationsRisque: { list: empty },
    risquesOpportunites: { list: empty, revuesDues: empty },
    permisTravail: { list: empty },
    consignationsLoto: { list: empty },
    inductionsSecurite: { list: empty },
    plansUrgence: { list: empty },
    secouristes: { list: empty },
    exercicesUrgence: {
      list: vi.fn(() => Promise.resolve({ data: [EXERCICE_PLANIFIE] })),
      create: (...a) => exerciceCreate(...a),
      realiser: (...a) => exerciceRealiser(...a),
      creerCapa: (...a) => exerciceCreerCapa(...a),
    },
    incidents: { list: empty, notificationsEnRetard: empty },
    declarationsCnss: { list: empty },
    analysesIncident: { list: empty },
    observationsSecurite: { list: empty },
    liensSignalement: { list: empty },
    signalementsPublics: { list: empty },
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import Risques from './Risques'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('Risques — Exercices d’urgence / drills (WIR234)', () => {
  it('planifie un nouvel exercice', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))

    await user.click(await screen.findByRole('button', { name: /Planifier un exercice/ }))
    await user.type(screen.getByLabelText("Plan d'urgence (id)"), '3')
    await user.type(screen.getByLabelText('Date prévue'), '2026-10-01')
    await user.click(screen.getByRole('button', { name: 'Planifier' }))

    await waitFor(() => expect(exerciceCreate).toHaveBeenCalledWith(
      expect.objectContaining({ plan: 3, date_prevue: '2026-10-01' }),
    ))
  })

  it('réalise un exercice planifié puis crée une CAPA d’écart', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))
    await screen.findAllByText('Évacuation atelier')

    await user.click(screen.getAllByRole('button', { name: 'Réaliser' })[0])
    await user.type(screen.getByLabelText("Durée d'évacuation (secondes)"), '180')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(exerciceRealiser).toHaveBeenCalledWith(
      61, expect.objectContaining({ duree_evacuation_secondes: '180' }),
    ))
  })
})
