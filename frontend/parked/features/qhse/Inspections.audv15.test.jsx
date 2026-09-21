import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* AUDV15 — 3 capacités de la diffusion de procédures (rediffusion sur
   nouvelle version, relance des retardataires, % conformité de lecture) et la
   thermographie IR (enregistrement + comparaison recette/suivi) étaient
   testées côté service mais sans AUCUN bouton/écran — voire, pour la
   thermographie, sans serializer ni viewset du tout. Réseau mocké. */

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

const {
  empty, rediffuser, relancerRetardataires, conformiteLecture,
  thermoCreate, thermoComparer,
} = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  rediffuser: vi.fn(() => Promise.resolve({ data: { id: 99, procedure: 8 } })),
  relancerRetardataires: vi.fn(() => Promise.resolve({ data: { total: 3 } })),
  conformiteLecture: vi.fn(() => Promise.resolve({
    data: { total: 4, lus: 3, pct: 75 },
  })),
  thermoCreate: vi.fn(() => Promise.resolve({
    data: { id: 1, classe_severite: 'intervention_requise', ncr: 42 },
  })),
  thermoComparer: vi.fn(() => Promise.resolve({
    data: {
      recette: { delta_t: '3.00' }, suivi: { delta_t: '9.00' }, delta: '6.00',
    },
  })),
}))

const PROCEDURE_ROW = {
  id: 8, reference: 'PQ-ACCUEIL-CHANTIER', titre: 'Accueil chantier',
  version: 2, statut: 'en_vigueur',
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    plansInspection: { list: empty },
    plansChantier: { list: empty },
    releves: { list: empty },
    grillesAudit: { list: empty },
    audits: { list: empty },
    notationsFinChantier: { list: empty },
    proceduresQualite: {
      list: () => Promise.resolve({ data: [PROCEDURE_ROW] }),
      create: vi.fn(), activer: vi.fn(), diffuser: vi.fn(),
      mesLecturesEnAttente: empty,
      conformiteLecture: (...a) => conformiteLecture(...a),
      rediffuserNouvelleVersion: (...a) => rediffuser(...a),
    },
    diffusionsProcedure: {
      marquerLu: vi.fn(),
      relancerRetardatairesLecture: (...a) => relancerRetardataires(...a),
    },
    retoursClient: { list: empty, moyenne: empty },
    plansControleReception: { list: empty },
    controlesReception: { list: empty },
    relevesThermographie: {
      list: empty,
      create: (...a) => thermoCreate(...a),
      comparer: (...a) => thermoComparer(...a),
    },
  },
}))

import Inspections from './Inspections'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('Inspections — rediffusion + relance + conformité de lecture (AUDV15)', () => {
  async function ouvrirClotureTab() {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))
    await waitFor(() => expect(screen.getAllByText('Accueil chantier').length).toBeGreaterThan(0))
    return user
  }

  it('rediffuse une nouvelle version vers la population de la version précédente', async () => {
    const user = await ouvrirClotureTab()
    await user.click(screen.getAllByRole('button', { name: 'Rediffuser (nouvelle version)' })[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Version précédente (id)'), '7')
    await user.click(within(dialog).getByRole('button', { name: 'Rediffuser' }))

    await waitFor(() => expect(rediffuser).toHaveBeenCalledWith(8, { procedure_precedente: 7 }))
  })

  it('relance les retardataires de lecture', async () => {
    const user = await ouvrirClotureTab()
    await user.click(screen.getByRole('button', { name: /Relancer les retardataires/ }))
    await waitFor(() => expect(relancerRetardataires).toHaveBeenCalled())
  })

  it('affiche le % de conformité de lecture d’une référence', async () => {
    const user = await ouvrirClotureTab()
    await user.type(screen.getByLabelText('Référence de procédure'), 'PQ-ACCUEIL-CHANTIER')
    await user.click(screen.getByRole('button', { name: /Conformité de lecture/ }))

    await waitFor(() => expect(conformiteLecture).toHaveBeenCalledWith(
      { reference: 'PQ-ACCUEIL-CHANTIER' },
    ))
    expect(await screen.findByText(/75 %/)).toBeInTheDocument()
  })
})

describe('Inspections — thermographie IR (AUDV15, XFSM14)', () => {
  it('enregistre un relevé de thermographie', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Thermographie IR' }))
    await user.click(await screen.findByRole('button', { name: /Nouveau relevé/ }))

    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Référence équipement'), 'STRING-3')
    await user.type(within(dialog).getByLabelText('ΔT mesuré (°C)'), '25')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(thermoCreate).toHaveBeenCalledWith(
      expect.objectContaining({ equipement_ref: 'STRING-3', delta_t: '25' }),
    ))
  })

  it('compare la dernière recette au dernier suivi', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Thermographie IR' }))
    await user.type(
      await screen.findByLabelText('Référence équipement (comparaison)'), 'ONDULEUR-2')
    await user.click(screen.getByRole('button', { name: /Comparer recette/ }))

    await waitFor(() => expect(thermoComparer).toHaveBeenCalledWith(
      { equipement_ref: 'ONDULEUR-2' },
    ))
    expect(await screen.findByText(/dérive \+6\.00°C/)).toBeInTheDocument()
  })
})
