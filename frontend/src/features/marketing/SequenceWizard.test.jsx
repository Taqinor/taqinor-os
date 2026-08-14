import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import {
  emptyWizardState, ajouterEtape, majEtape, calendrierPrevu, blocageWhatsapp,
  peutActiver,
} from './sequenceWizard'

describe('sequenceWizard (logique pure, NTMKT30)', () => {
  it('calendrierPrevu trie les étapes par délai croissant', () => {
    let s = ajouterEtape(emptyWizardState())
    s = majEtape(s, 0, { delai_jours: 7, canal: 'sms' })
    s = ajouterEtape(s)
    s = majEtape(s, 1, { delai_jours: 0, canal: 'email' })
    const cal = calendrierPrevu(s.etapes)
    expect(cal).toEqual([{ jour: 'J+0', canal: 'email' }, { jour: 'J+7', canal: 'sms' }])
  })

  it('bloque tant que WhatsApp est utilisé sans confirmation BSP', () => {
    let s = ajouterEtape(emptyWizardState())
    s = majEtape(s, 0, { canal: 'whatsapp' })
    expect(blocageWhatsapp(s)).toBe(true)
    expect(peutActiver({ ...s, nom: 'X' })).toBe(false)
    s = { ...s, whatsappConfigure: true }
    expect(blocageWhatsapp(s)).toBe(false)
  })

  it('peutActiver exige un nom et au moins une étape', () => {
    expect(peutActiver(emptyWizardState())).toBe(false)
    expect(peutActiver({ ...emptyWizardState(), nom: 'X' })).toBe(false)
    const s = ajouterEtape({ ...emptyWizardState(), nom: 'X' })
    expect(peutActiver(s)).toBe(true)
  })
})

const mocks = vi.hoisted(() => ({
  sequencesCreate: vi.fn(),
  etapesCreate: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    sequences: { create: mocks.sequencesCreate },
    etapesSequence: { create: mocks.etapesCreate },
  },
}))

import SequenceWizard from './SequenceWizard.jsx'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.sequencesCreate.mockResolvedValue({ data: { id: 9 } })
  mocks.etapesCreate.mockResolvedValue({ data: { id: 1 } })
})

describe('SequenceWizard (composant, NTMKT30)', () => {
  it('créer une séquence à 3 étapes produit les mêmes EtapeSequence', async () => {
    const onCreated = vi.fn()
    render(<MemoryRouter><SequenceWizard onCreated={onCreated} /></MemoryRouter>)

    fireEvent.change(screen.getByTestId('wizard-sequence-nom'),
      { target: { value: 'Relance devis' } })
    fireEvent.click(screen.getByTestId('wizard-ajouter-etape'))
    fireEvent.click(screen.getByTestId('wizard-ajouter-etape'))
    fireEvent.click(screen.getByTestId('wizard-ajouter-etape'))
    fireEvent.change(screen.getByTestId('wizard-etape-1-delai'), { target: { value: '3' } })
    fireEvent.change(screen.getByTestId('wizard-etape-2-delai'), { target: { value: '7' } })

    fireEvent.click(screen.getByTestId('wizard-confirmer'))

    await waitFor(() => expect(mocks.etapesCreate).toHaveBeenCalledTimes(3))
    expect(mocks.sequencesCreate).toHaveBeenCalledWith({ nom: 'Relance devis' })
    expect(mocks.etapesCreate).toHaveBeenNthCalledWith(2, expect.objectContaining({
      sequence: 9, ordre: 2, delai_jours: 3,
    }))
    expect(onCreated).toHaveBeenCalledWith({ id: 9 })
  })

  it('le bouton reste désactivé si WhatsApp est choisi sans confirmation', () => {
    render(<MemoryRouter><SequenceWizard /></MemoryRouter>)
    fireEvent.change(screen.getByTestId('wizard-sequence-nom'), { target: { value: 'X' } })
    fireEvent.click(screen.getByTestId('wizard-ajouter-etape'))
    fireEvent.change(screen.getByTestId('wizard-etape-0-canal'),
      { target: { value: 'whatsapp' } })
    expect(screen.getByTestId('wizard-confirmer')).toBeDisabled()
    expect(screen.getByTestId('wizard-blocage-whatsapp')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('wizard-whatsapp-confirme'))
    expect(screen.getByTestId('wizard-confirmer')).not.toBeDisabled()
  })
})
