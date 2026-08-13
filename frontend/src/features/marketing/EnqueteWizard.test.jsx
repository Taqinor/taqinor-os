import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { emptyWizardState, choisirType, peutPublier } from './enqueteWizard'

describe('enqueteWizard (logique pure, NTMKT32)', () => {
  it('« satisfaction post-installation » pré-remplit 4 questions éditables', () => {
    const s = choisirType(emptyWizardState(), 'satisfaction_installation')
    expect(s.questions).toHaveLength(4)
    expect(s.questions[0].libelle).toContain('installation')
  })

  it('« personnalisé » démarre sans question', () => {
    const s = choisirType(emptyWizardState(), 'personnalise')
    expect(s.questions).toHaveLength(0)
  })

  it('peutPublier exige un type + titre + au moins une question', () => {
    expect(peutPublier(emptyWizardState())).toBe(false)
    const s = choisirType(emptyWizardState(), 'nps')
    expect(peutPublier(s)).toBe(false)
    expect(peutPublier({ ...s, titre: 'Enquête satisfaction' })).toBe(true)
  })
})

const mocks = vi.hoisted(() => ({
  enquetesCreate: vi.fn(),
  segmentsList: vi.fn(),
  listesList: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    enquetes: { create: mocks.enquetesCreate },
    segments: { list: mocks.segmentsList },
    listes: { list: mocks.listesList },
  },
}))

import EnqueteWizard from './EnqueteWizard.jsx'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.segmentsList.mockResolvedValue({ data: [] })
  mocks.listesList.mockResolvedValue({ data: [] })
  mocks.enquetesCreate.mockResolvedValue({ data: { id: 5 } })
})

describe('EnqueteWizard (composant, NTMKT32)', () => {
  it("choisir un type pré-remplit les questions et permet de publier", async () => {
    const onCreated = vi.fn()
    render(<MemoryRouter><EnqueteWizard onCreated={onCreated} /></MemoryRouter>)

    fireEvent.click(await screen.findByTestId('wizard-type-satisfaction_sav'))
    expect(screen.getByTestId('wizard-question-0')).toBeInTheDocument()
    expect(screen.getByTestId('wizard-question-3')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('wizard-enquete-titre'),
      { target: { value: 'Satisfaction SAV Q3' } })
    fireEvent.click(screen.getByTestId('wizard-publier'))

    await waitFor(() => expect(mocks.enquetesCreate).toHaveBeenCalledTimes(1))
    expect(mocks.enquetesCreate).toHaveBeenCalledWith(expect.objectContaining({
      titre: 'Satisfaction SAV Q3',
    }))
    expect(onCreated).toHaveBeenCalledWith({ id: 5 })
  })

  it('le bouton publier reste désactivé sans titre', async () => {
    render(<MemoryRouter><EnqueteWizard /></MemoryRouter>)
    fireEvent.click(await screen.findByTestId('wizard-type-nps'))
    expect(screen.getByTestId('wizard-publier')).toBeDisabled()
  })
})
