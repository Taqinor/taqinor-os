import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR235 — les 3 documents terrain bilingues XQHS27 (causerie, permis de
   travail, induction sécurité) n'avaient de bouton PDF que pour la causerie
   (frontend/src/features/rh/Hse.jsx). On vérifie que Risques.jsx expose
   désormais « PDF (FR) / (AR) » sur les listes Permis de travail et
   Inductions sécurité, en blob avec le bon `lang`. */

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

const { empty, permisPdf, inductionPdf } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  permisPdf: vi.fn(() => Promise.resolve({ data: new Blob(['%PDF']) })),
  inductionPdf: vi.fn(() => Promise.resolve({ data: new Blob(['%PDF']) })),
}))

const PERMIS_ROW = {
  id: 10, reference: 'PT-000010', titre: 'Soudure toiture', type_permis: 'point_chaud',
  type_permis_display: 'Point chaud', statut: 'valide', date_fin: null,
}
const INDUCTION_ROW = {
  id: 40, salarie_nom: 'A. Test', date_induction: '2026-01-05', statut: 'realisee',
}

vi.mock('../../api/qhseApi', () => ({
  default: {
    evaluationsRisque: { list: empty },
    risquesOpportunites: { list: empty, revuesDues: empty },
    permisTravail: {
      list: vi.fn(() => Promise.resolve({ data: [PERMIS_ROW] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      valider: vi.fn(() => Promise.resolve({ data: {} })),
      cloturer: vi.fn(() => Promise.resolve({ data: {} })),
      pdf: (...a) => permisPdf(...a),
    },
    consignationsLoto: { list: empty },
    inductionsSecurite: {
      list: vi.fn(() => Promise.resolve({ data: [INDUCTION_ROW] })),
      pdf: (...a) => inductionPdf(...a),
    },
    plansUrgence: { list: empty },
    secouristes: { list: empty },
    exercicesUrgence: { list: empty },
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

async function ouvrirMenuLigne(user, texte) {
  await waitFor(() => expect(screen.getAllByText(texte).length).toBeGreaterThan(0))
  const kebabs = screen.getAllByLabelText("Plus d'actions sur la ligne")
  await user.click(kebabs[0])
}

describe('Risques — PDF terrain bilingues (WIR235)', () => {
  it('télécharge le PDF (FR) puis (AR) d’un permis de travail', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Permis & LOTO' }))
    await ouvrirMenuLigne(user, 'Soudure toiture')

    await user.click(await screen.findByRole('menuitem', { name: 'PDF (FR)' }))
    await waitFor(() => expect(permisPdf).toHaveBeenCalledWith(10, { lang: 'fr' }))

    await ouvrirMenuLigne(user, 'Soudure toiture')
    await user.click(await screen.findByRole('menuitem', { name: 'PDF (AR)' }))
    await waitFor(() => expect(permisPdf).toHaveBeenCalledWith(10, { lang: 'ar' }))
  })

  it('télécharge le PDF (FR) d’une induction sécurité', async () => {
    const user = userEvent.setup()
    withProviders(<Risques />)
    await user.click(screen.getByRole('tab', { name: 'Préparation site' }))
    await ouvrirMenuLigne(user, 'A. Test')

    await user.click(await screen.findByRole('menuitem', { name: 'PDF (FR)' }))
    await waitFor(() => expect(inductionPdf).toHaveBeenCalledWith(40, { lang: 'fr' }))
  })
})
