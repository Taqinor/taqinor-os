import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* WIR124 — les 4 onglets d'Inspections (ITP, Audits, Procédures qualité, Retours
   client) étaient lecture seule alors que le backend est complet. On vérifie que
   chaque onglet expose désormais une action d'écriture, et que le chemin de
   création d'une procédure fonctionne de bout en bout. Réseau mocké.
   WIR278 — diffusion des procédures (action `diffuser/`, jamais appelée côté
   écran) + accusé de lecture (« Marquer comme lue », utilisateur COURANT
   uniquement). Le mock de `diffuser` IMPORTE le contrat committé
   (apps/qhse/contract_samples/procedure_qualite_diffuser.json, PACT10/13). */

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

const { empty, procedureCreate, procedureDiffuser, marquerLu } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  procedureCreate: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
  procedureDiffuser: vi.fn(),
  marquerLu: vi.fn(() => Promise.resolve({ data: {} })),
}))

const PROCEDURE_ROW = {
  id: 8, reference: 'PQ-ACCUEIL-CHANTIER', titre: 'Accueil chantier',
  version: 2, statut: 'en_vigueur',
}
const LECTURE_ROW = {
  id: 20, diffusion: 12, procedure_reference: 'PQ-ACCUEIL-CHANTIER',
  procedure_titre: 'Accueil chantier', procedure_version: 2,
  date_diffusion: '2026-08-01T09:00:00Z',
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    plansInspection: { list: empty },
    plansChantier: { list: empty, instancier: vi.fn(() => Promise.resolve({ data: {} })) },
    releves: { list: empty },
    grillesAudit: { list: empty, create: vi.fn() },
    audits: { list: empty, create: vi.fn(), calculerScore: vi.fn(), leverNcr: vi.fn() },
    notationsFinChantier: { list: empty },
    proceduresQualite: {
      list: () => Promise.resolve({ data: [PROCEDURE_ROW] }),
      create: (...a) => procedureCreate(...a), activer: vi.fn(),
      mesLecturesEnAttente: () => Promise.resolve({ data: [LECTURE_ROW] }),
      diffuser: (...a) => procedureDiffuser(...a),
    },
    diffusionsProcedure: {
      marquerLu: (...a) => marquerLu(...a),
    },
    retoursClient: {
      list: empty,
      create: vi.fn(),
      moyenne: () => Promise.resolve({ data: { moyenne: 4.2, total: 3 } }),
    },
  },
}))

import Inspections from './Inspections'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  procedureDiffuser.mockResolvedValue(reponseContrat('qhse', 'procedure_qualite_diffuser'))
})

describe('Inspections — actions d\'écriture (WIR124)', () => {
  it('l\'onglet ITP propose d\'instancier un plan', async () => {
    withProviders(<Inspections />)
    await waitFor(() => expect(screen.getByRole('button', { name: /Instancier un plan/ })).toBeTruthy())
  })

  it('l\'onglet Audits propose de créer une grille et démarrer un audit', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Audits' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Nouvelle grille/ })).toBeTruthy())
    expect(screen.getByRole('button', { name: /Démarrer un audit/ })).toBeTruthy()
  })

  it('l\'onglet Fin de chantier affiche la moyenne et permet de créer une procédure', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))

    await waitFor(() => expect(screen.getByTestId('retours-moyenne')).toBeTruthy())
    expect(screen.getByText(/4\.2\/5/)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: /Nouvelle procédure/ }))
    await waitFor(() => expect(screen.getByText('Nouvelle procédure qualité')).toBeTruthy())

    fireEvent.change(screen.getByLabelText('Référence'), { target: { value: 'PQ-001' } })
    fireEvent.change(screen.getByLabelText('Titre'), { target: { value: 'Contrôle pose' } })
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(procedureCreate).toHaveBeenCalledWith(
      expect.objectContaining({ reference: 'PQ-001', titre: 'Contrôle pose', version: 1 }),
    ))
  })

  it('l\'onglet Fin de chantier propose de créer un retour client', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Nouveau retour/ })).toBeTruthy())
  })
})

describe('Inspections — diffusion des procédures + accusé de lecture (WIR278)', () => {
  it('diffuse une version à une population d\'utilisateurs (contrat committé importé)', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))
    await waitFor(() => expect(screen.getAllByText('Accueil chantier').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Diffuser cette version' })[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByLabelText('Destinataires (ids utilisateur, séparés par des virgules)'),
      '5, 7, 9')
    await user.click(within(dialog).getByRole('button', { name: 'Diffuser' }))

    await waitFor(() => expect(procedureDiffuser).toHaveBeenCalledWith(
      8, { user_ids: [5, 7, 9] }))
  })

  it('marque une lecture en attente comme lue (utilisateur courant uniquement)', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Marquer comme lue' }).length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Marquer comme lue' })[0])
    // `r.diffusion` (12), jamais l'id de l'AccuseLecture (20) : marquer-lu
    // agit sur la DIFFUSION, pour l'utilisateur courant côté serveur.
    await waitFor(() => expect(marquerLu).toHaveBeenCalledWith(12))
  })
})
