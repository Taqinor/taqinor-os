import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* FE-XQHS17 — le registre BBS (observations sécurité comportementales) était
   en LECTURE + conversion seulement : aucun écran ne permettait la capture
   terrain que le modèle `ObservationSecurite` décrit pourtant comme sa raison
   d'être. On vérifie que l'onglet expose désormais un formulaire de capture
   rapide qui poste bien au serveur. Réseau mocké. */

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

const { empty, observationCreate, roList, roRevuesDues, roCreate } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  observationCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  roList: vi.fn(() => Promise.resolve({
    data: [{
      id: 5, type_ro: 'risque', type_ro_display: 'Risque',
      processus: 'Achats', description: 'Rupture fournisseur onduleurs',
      criticite_inherente: 16, criticite_residuelle: 6, date_revue: '2026-09-01',
    }],
  })),
  roRevuesDues: vi.fn(() => Promise.resolve({ data: [] })),
  roCreate: vi.fn(() => Promise.resolve({ data: { id: 6 } })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    evaluationsRisque: { list: empty },
    risquesOpportunites: {
      list: (...a) => roList(...a),
      revuesDues: (...a) => roRevuesDues(...a),
      create: (...a) => roCreate(...a),
    },
    permisTravail: { list: empty },
    consignationsLoto: { list: empty },
    inductionsSecurite: { list: empty },
    plansUrgence: { list: empty },
    secouristes: { list: empty },
    exercicesUrgence: { list: empty },
    incidents: { list: empty },
    declarationsCnss: { list: empty },
    analysesIncident: { list: empty },
    observationsSecurite: {
      list: empty,
      create: (...a) => observationCreate(...a),
    },
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

describe('Risques — Observations BBS (FE-XQHS17)', () => {
  it('capture une observation terrain et la poste au serveur', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Observations BBS' }))

    await user.click(await screen.findByRole('button', { name: /Nouvelle observation/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByLabelText('Ce que j’ai vu'),
      'Échafaudage sans garde-corps',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(observationCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        description: 'Échafaudage sans garde-corps',
        type_observation: 'a_risque',
        categorie: 'autre',
        feedback_donne: false,
      }),
    ))
    // La date du jour est posée par défaut (capture terrain, zéro friction).
    expect(observationCreate.mock.calls[0][0].date_observation)
      .toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('refuse une observation sans description (pas d’appel réseau)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Observations BBS' }))
    await user.click(await screen.findByRole('button', { name: /Nouvelle observation/ }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))
    expect(observationCreate).not.toHaveBeenCalled()
  })
})

/* FE-XQHS14 — `RisqueOpportunite` (registre SMQ, ISO 6.1) avait son viewset,
   ses criticités serveur et son action `revues-dues/`, mais AUCUN écran : le
   client API ne le nommait même pas. */
describe('Risques — Risques & opportunités SMQ (FE-XQHS14)', () => {
  it('liste le registre SMQ avec ses criticités inhérente et résiduelle', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Risques & opportunités' }))

    // DataTable rend table desktop + repli carte mobile : getAllByText.
    await waitFor(() => expect(
      screen.getAllByText('Rupture fournisseur onduleurs').length,
    ).toBeGreaterThan(0))
    expect(screen.getAllByText('16').length).toBeGreaterThan(0)
    expect(screen.getAllByText('6').length).toBeGreaterThan(0)
  })

  it('bascule sur les revues dues (action `revues-dues/`, jusqu’ici sans appelant)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Risques & opportunités' }))
    await waitFor(() => expect(roList).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: /Revues dues/ }))
    await waitFor(() => expect(roRevuesDues).toHaveBeenCalled())
  })

  it('crée un risque SMQ sans jamais poster de criticité (calcul serveur)', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Risques & opportunités' }))

    await user.click(await screen.findByRole('button', { name: /Nouveau risque \/ opportunité/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByLabelText('Description'), 'Dépendance mono-fournisseur',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(roCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        type_ro: 'risque', description: 'Dépendance mono-fournisseur',
        probabilite_inherente: 1, gravite_inherente: 1,
      }),
    ))
    const posted = roCreate.mock.calls[0][0]
    expect(posted).not.toHaveProperty('criticite_inherente')
    expect(posted).not.toHaveProperty('criticite_residuelle')
  })
})
