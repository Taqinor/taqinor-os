import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import {
  emptyWizardState, choisirObjectif, etapeValide, buildPayload,
} from './campagneWizard'

describe('campagneWizard (logique pure, NTMKT29)', () => {
  it("choisir l'objectif pré-remplit le canal par défaut", () => {
    const s = choisirObjectif(emptyWizardState(), 'relance')
    expect(s.objectif).toBe('relance')
    expect(s.canal).toBe('sms')
  })

  it("étape 1 invalide sans objectif choisi", () => {
    expect(etapeValide(emptyWizardState())).toBe(false)
  })

  it('étape 2 exige une liste OU un segment', () => {
    const s = { ...emptyWizardState(), etape: 2, listes: [], segmentId: '' }
    expect(etapeValide(s)).toBe(false)
    expect(etapeValide({ ...s, listes: [1] })).toBe(true)
    expect(etapeValide({ ...s, segmentId: '3' })).toBe(true)
  })

  it('buildPayload produit la même forme que CampagneForm.emptyForm()', () => {
    const payload = buildPayload({
      ...emptyWizardState(), objectif: 'promo', canal: 'email',
      objet: 'Objet', corps: 'Corps', listes: [1, 2], planifiee_le: '',
    })
    expect(payload).toEqual(expect.objectContaining({
      canal: 'email', objet: 'Objet', corps: 'Corps', listes: [1, 2],
      variantes_langue: {}, ab_test: {},
    }))
    expect(typeof payload.nom).toBe('string')
    expect(payload.nom.length).toBeGreaterThan(0)
  })
})

const mocks = vi.hoisted(() => ({
  listesList: vi.fn(),
  segmentsList: vi.fn(),
  campagnesCreate: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    listes: { list: mocks.listesList },
    segments: { list: mocks.segmentsList },
    campagnes: { create: mocks.campagnesCreate },
  },
}))

import CampagneWizard from './CampagneWizard.jsx'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listesList.mockResolvedValue({ data: [{ id: 1, nom: 'Clients actifs' }] })
  mocks.segmentsList.mockResolvedValue({ data: [{ id: 3, nom: 'MQL chauds' }] })
  mocks.campagnesCreate.mockResolvedValue({ data: { id: 42 } })
})

describe('CampagneWizard (composant, NTMKT29)', () => {
  it('compléter les 4 étapes crée une campagne', async () => {
    const onCreated = vi.fn()
    render(<MemoryRouter><CampagneWizard onCreated={onCreated} /></MemoryRouter>)

    fireEvent.click(await screen.findByTestId('wizard-objectif-promo'))
    fireEvent.click(screen.getByTestId('wizard-suivant'))

    await screen.findByTestId('wizard-etape-audience')
    fireEvent.change(screen.getByTestId('wizard-audience-segment'),
      { target: { value: '3' } })
    fireEvent.click(screen.getByTestId('wizard-suivant'))

    await screen.findByTestId('wizard-etape-contenu')
    fireEvent.change(screen.getByTestId('wizard-objet'), { target: { value: 'Objet promo' } })
    fireEvent.click(screen.getByTestId('wizard-suivant'))

    await screen.findByTestId('wizard-etape-resume')
    fireEvent.click(screen.getByTestId('wizard-confirmer'))

    await waitFor(() => expect(mocks.campagnesCreate).toHaveBeenCalledTimes(1))
    expect(onCreated).toHaveBeenCalledWith({ id: 42 })
  })

  it("abandon à mi-parcours ne crée aucun brouillon orphelin", async () => {
    const onCancel = vi.fn()
    render(<MemoryRouter><CampagneWizard onCancel={onCancel} /></MemoryRouter>)

    fireEvent.click(await screen.findByTestId('wizard-objectif-newsletter'))
    fireEvent.click(screen.getByTestId('wizard-suivant'))
    await screen.findByTestId('wizard-etape-audience')
    fireEvent.click(screen.getByTestId('wizard-annuler'))

    expect(mocks.campagnesCreate).not.toHaveBeenCalled()
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it("« Suivant » reste désactivé tant que l'étape n'est pas valide", async () => {
    render(<MemoryRouter><CampagneWizard /></MemoryRouter>)
    await screen.findByTestId('wizard-etape-objectif')
    expect(screen.getByTestId('wizard-suivant')).toBeDisabled()
  })
})
