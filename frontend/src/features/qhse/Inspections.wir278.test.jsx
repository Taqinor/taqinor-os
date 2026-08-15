import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR278 — « Diffuser cette version » (sur une procédure EN VIGUEUR) et
   « Marquer comme lue » (sur « Mes lectures en attente ») n'avaient aucun
   bouton côté écran alors que le backend (WIR277) expose déjà
   `proceduresQualite.diffuser` et `diffusionsProcedure.marquerLu`. Réseau
   mocké. */

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

const PROCEDURE_EN_VIGUEUR = {
  id: 30, reference: 'PRO-QUAL-004', titre: 'Réception des modules photovoltaïques',
  version: 3, statut: 'en_vigueur', statut_display: 'En vigueur',
}
const LECTURE_EN_ATTENTE = {
  id: 12, diffusion: 12, procedure_reference: 'PRO-QUAL-004',
  procedure_titre: 'Réception des modules photovoltaïques', procedure_version: 3,
  date_diffusion: '2026-08-01T10:15:00Z', lu_le: null,
}

const { empty, diffuser, marquerLu } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  diffuser: vi.fn(() => Promise.resolve({ data: {} })),
  marquerLu: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    plansInspection: { list: empty },
    plansChantier: { list: empty, instancier: vi.fn() },
    releves: { list: empty },
    grillesAudit: { list: empty, create: vi.fn() },
    audits: { list: empty, create: vi.fn(), calculerScore: vi.fn(), leverNcr: vi.fn() },
    notationsFinChantier: { list: empty },
    proceduresQualite: {
      list: vi.fn(() => Promise.resolve({ data: [PROCEDURE_EN_VIGUEUR] })),
      create: vi.fn(), activer: vi.fn(),
      mesLecturesEnAttente: vi.fn(() => Promise.resolve({ data: [LECTURE_EN_ATTENTE] })),
      diffuser: (...a) => diffuser(...a),
    },
    diffusionsProcedure: { marquerLu: (...a) => marquerLu(...a) },
    retoursClient: { list: empty, create: vi.fn(), moyenne: empty },
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import Inspections from './Inspections'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('Inspections — diffusion & lecture des procédures (WIR278)', () => {
  it('diffuse la version courante à une liste de destinataires', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))
    await screen.findByText('PRO-QUAL-004')

    const rowMenu = await screen.findByRole('button', { name: "Plus d'actions sur la ligne" })
    await user.click(rowMenu)
    await user.click(await screen.findByRole('menuitem', { name: 'Diffuser cette version' }))

    await user.type(await screen.findByLabelText(
      'Destinataires (ids utilisateurs, séparés par virgule)'), '4, 7, 9')
    await user.click(screen.getByRole('button', { name: 'Diffuser' }))

    await waitFor(() => expect(diffuser).toHaveBeenCalledWith(30, { user_ids: [4, 7, 9] }))
  })

  it('accuse la lecture d’une diffusion en attente', async () => {
    const user = userEvent.setup()
    withProviders(<Inspections />)
    await user.click(screen.getByRole('tab', { name: 'Fin de chantier' }))
    await screen.findByText('Mes lectures en attente')

    const rowMenu = await screen.findAllByRole('button', { name: "Plus d'actions sur la ligne" })
    await user.click(rowMenu[rowMenu.length - 1])
    await user.click(await screen.findByRole('menuitem', { name: 'Marquer comme lue' }))

    await waitFor(() => expect(marquerLu).toHaveBeenCalledWith(12))
  })
})
