import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB128 — Écran « Tests terrain » (préflight d'autonomie) : 7 tests FT1..FT7,
   consignation d'un résultat mesuré, proposition de structures PAUSÉES. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  recordResult: vi.fn(),
  proposeStructures: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    fieldTests: {
      list: mocks.list,
      recordResult: mocks.recordResult,
      proposeStructures: mocks.proposeStructures,
    },
  },
}))

import FieldTestsScreen from './FieldTestsScreen'

const renderScreen = () => render(<MemoryRouter><FieldTestsScreen /></MemoryRouter>)

function makeTest(n) {
  return {
    ft: `FT${n}`,
    label_fr: `Libellé du test ${n}`,
    question_fr: `Question du test ${n} ?`,
    protocole_fr: ['étape 1', 'étape 2', 'étape 3'],
    mesure_fr: `Mesure du test ${n}`,
    plafond_mad: 30,
    tranche: n === 1,
    valeur_mesuree: n === 1 ? '18%' : '',
    preuve: n === 1 ? 'capture-1.png' : '',
    mesure_le: n === 1 ? '2026-09-01' : '',
    constantes: [
      {
        cle: `constante_${n}`, label_fr: `Constante ${n}`, valeur: 20,
        unite: '%', source: 'research', consumer: 'budget_applier', tranche: n === 1,
      },
    ],
  }
}

const PAYLOAD = {
  plafond_mad: 30,
  runbook: 'docs/engine/field-tests.md',
  toutes_tranchees: false,
  constantes_en_attente: ['constante_2', 'constante_3', 'constante_4', 'constante_5', 'constante_6', 'constante_7'],
  tests: [1, 2, 3, 4, 5, 6, 7].map(makeTest),
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: PAYLOAD })
  mocks.recordResult.mockResolvedValue({
    data: { ft: 'FT2', tranche: true, valeur_mesuree: '25%', preuve: '', mesure_le: '2026-09-20', toutes_tranchees: false, constantes_en_attente: [] },
  })
  mocks.proposeStructures.mockResolvedValue({
    data: { ft: 'FT1', plafond_mad: 30, actions: [{ id: 1, kind: 'create_ad', reason_fr: 'test' }, { id: 2, kind: 'create_ad', reason_fr: 'test' }] },
  })
})

describe('FieldTestsScreen', () => {
  it('affiche les 7 lignes FT depuis le payload mocké', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-table')).toBeTruthy())
    for (let n = 1; n <= 7; n++) {
      expect(screen.getByTestId(`ae-tests-terrain-row-FT${n}`)).toBeTruthy()
    }
  })

  it('affiche le plafond depuis plafond_mad', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-plafond')).toBeTruthy())
    expect(screen.getByTestId('ae-tests-terrain-plafond').textContent).toContain('30 MAD')
  })

  it('soumet une valeur mesurée et appelle recordResult avec le bon ft + payload', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-row-FT2')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-tests-terrain-valeur-FT2'), { target: { value: '25%' } })
    fireEvent.change(screen.getByTestId('ae-tests-terrain-preuve-FT2'), { target: { value: 'capture-2.png' } })
    fireEvent.change(screen.getByTestId('ae-tests-terrain-date-FT2'), { target: { value: '2026-09-20' } })
    fireEvent.click(screen.getByTestId('ae-tests-terrain-submit-FT2'))
    await waitFor(() => expect(mocks.recordResult).toHaveBeenCalled())
    expect(mocks.recordResult).toHaveBeenCalledWith('FT2', {
      measured_value: '25%', evidence: 'capture-2.png', measured_on: '2026-09-20',
    })
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-msg')).toBeTruthy())
    expect(screen.getByTestId('ae-tests-terrain-msg').textContent).toContain('FT2')
  })

  it("omet measured_on quand la date est vide (jamais '')", async () => {
    // PUB-P8/C4 — la case date est OPTIONNELLE : la clé est absente du corps,
    // le serveur date au jour courant. Envoyer '' faisait échouer la saisie.
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-row-FT2')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-tests-terrain-valeur-FT2'), { target: { value: '25%' } })
    fireEvent.click(screen.getByTestId('ae-tests-terrain-submit-FT2'))
    await waitFor(() => expect(mocks.recordResult).toHaveBeenCalled())
    expect(mocks.recordResult).toHaveBeenCalledWith('FT2', {
      measured_value: '25%', evidence: '',
    })
    expect(Object.keys(mocks.recordResult.mock.calls[0][1])).not.toContain('measured_on')
  })

  it('affiche la raison FR du serveur quand les structures sont refusées', async () => {
    // PUB-P8/C5 — devise du compte ≠ MAD : la raison motivée doit s'afficher,
    // jamais un « impossible » muet.
    mocks.proposeStructures.mockRejectedValueOnce({
      response: { data: { detail: 'Devise du compte USD ≠ MAD — plafond micro-test 30 MAD non convertible sans décision fondateur.' } },
    })
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-structures-FT1')).toBeTruthy())
    fireEvent.click(screen.getByTestId('ae-tests-terrain-structures-FT1'))
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-err')).toBeTruthy())
    expect(screen.getByTestId('ae-tests-terrain-err').textContent).toContain('Devise du compte USD')
    expect(screen.getByTestId('ae-tests-terrain-err').textContent).toContain('décision fondateur')
  })

  it('ne soumet rien si la valeur mesurée est vide', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-row-FT3')).toBeTruthy())
    fireEvent.click(screen.getByTestId('ae-tests-terrain-submit-FT3'))
    expect(mocks.recordResult).not.toHaveBeenCalled()
  })

  it('propose des structures et affiche le nombre de propositions', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-structures-FT1')).toBeTruthy())
    fireEvent.click(screen.getByTestId('ae-tests-terrain-structures-FT1'))
    await waitFor(() => expect(mocks.proposeStructures).toHaveBeenCalledWith('FT1', { city: '' }))
    expect(screen.getByTestId('ae-tests-terrain-msg').textContent).toContain('2')
  })

  it('affiche une erreur au chargement sans planter', async () => {
    mocks.list.mockRejectedValueOnce(new Error('boom'))
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-tests-terrain-err')).toBeTruthy())
    expect(screen.queryByTestId('ae-tests-terrain-table')).toBeNull()
  })
})
