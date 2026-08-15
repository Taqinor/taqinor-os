import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* WIR276 — les 5 registres ISO exposés par WIR275 (campagnes de rappel,
   certifications, programme d'audit, réunions/revues de direction,
   objectifs 6.2) n'avaient AUCUN écran. Les charges utiles viennent des
   contrats commités (PACT10) : `apps/qhse/contract_samples/*.json`, jamais
   écrites à la main — garde `scripts/check_api_shapes.py`. */

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

const CAMPAGNE = exempleContrat('qhse', 'campagne_rappel')
const CERTIFICATION = exempleContrat('qhse', 'certification')
const AUDIT_PLANIFIE = exempleContrat('qhse', 'audit_planifie')
const REUNION = exempleContrat('qhse', 'reunion_qhse')
const OBJECTIF = exempleContrat('qhse', 'objectif_qhse')

const { empty, campagneCreate, certifCreate } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  campagneCreate: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  certifCreate: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    campagnesRappel: {
      list: () => Promise.resolve({ data: [CAMPAGNE] }),
      create: (...a) => campagneCreate(...a),
    },
    certifications: {
      list: () => Promise.resolve({ data: [CERTIFICATION] }),
      create: (...a) => certifCreate(...a),
    },
    programmesAudit: { list: empty, create: vi.fn() },
    auditsPlanifies: { list: () => Promise.resolve({ data: [AUDIT_PLANIFIE] }) },
    reunionsQhse: { list: () => Promise.resolve({ data: [REUNION] }), create: vi.fn() },
    objectifsQhse: { list: () => Promise.resolve({ data: [OBJECTIF] }), create: vi.fn() },
  },
}))

import RegistresIso from './RegistresIso'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('RegistresIso — onglet Rappels produit (WIR276)', () => {
  it('affiche la campagne de rappel avec les clés du contrat', async () => {
    withProviders(<RegistresIso />)
    expect(await screen.findByText(CAMPAGNE.titre)).toBeTruthy()
    expect(screen.getByText(CAMPAGNE.gravite_display)).toBeTruthy()
  })

  it('crée une campagne de bout en bout', async () => {
    const user = userEvent.setup()
    withProviders(<RegistresIso />)

    await user.click(await screen.findByRole('button', { name: /Nouvelle campagne/ }))
    await waitFor(() => expect(screen.getAllByText('Nouvelle campagne de rappel').length)
      .toBeGreaterThan(0))

    await user.type(screen.getByLabelText('Titre'), 'Rappel lot 9')
    await user.type(screen.getByLabelText('Produit (id)'), '41')
    await user.type(screen.getByLabelText('Motif'), 'Défaut détecté')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(campagneCreate).toHaveBeenCalledWith(
      expect.objectContaining({ titre: 'Rappel lot 9', produit: 41, motif: 'Défaut détecté' }),
    ))
  })
})

describe('RegistresIso — onglet Certifications (WIR276)', () => {
  it('affiche la certification avec son statut calculé', async () => {
    const user = userEvent.setup()
    withProviders(<RegistresIso />)
    await user.click(await screen.findByRole('tab', { name: 'Certifications' }))
    expect(await screen.findByText(CERTIFICATION.organisme)).toBeTruthy()
  })
})

describe('RegistresIso — onglet Programme d\'audit (WIR276)', () => {
  it('affiche l’audit planifié avec l’indépendance advisory', async () => {
    const user = userEvent.setup()
    withProviders(<RegistresIso />)
    await user.click(await screen.findByRole('tab', { name: "Programme d'audit" }))
    expect(await screen.findByText(AUDIT_PLANIFIE.processus_domaine)).toBeTruthy()
    expect(screen.getByText('À vérifier')).toBeTruthy()
  })
})

describe('RegistresIso — onglet Revues de direction (WIR276)', () => {
  it('affiche la réunion avec son type', async () => {
    const user = userEvent.setup()
    withProviders(<RegistresIso />)
    await user.click(await screen.findByRole('tab', { name: 'Revues de direction' }))
    expect(await screen.findByText(REUNION.type_reunion_display)).toBeTruthy()
  })
})

describe('RegistresIso — onglet Objectifs QHSE (WIR276)', () => {
  it('affiche l’objectif avec sa dernière revue', async () => {
    const user = userEvent.setup()
    withProviders(<RegistresIso />)
    await user.click(await screen.findByRole('tab', { name: 'Objectifs QHSE' }))
    expect(await screen.findByText(OBJECTIF.intitule)).toBeTruthy()
  })
})
