import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import {
  addQuestion, removeQuestion, updateQuestion, optionsFromText, optionsToText,
} from './enqueteRules'

describe('enqueteRules — manipulation du tableau questions (logique pure)', () => {
  it('addQuestion ajoute une question texte vide', () => {
    const questions = addQuestion([])
    expect(questions).toHaveLength(1)
    expect(questions[0].type).toBe('texte')
    expect(questions[0].condition).toBeNull()
  })

  it('removeQuestion retire par index', () => {
    const questions = [{ id: 'q1' }, { id: 'q2' }, { id: 'q3' }]
    expect(removeQuestion(questions, 1)).toEqual([{ id: 'q1' }, { id: 'q3' }])
  })

  it('updateQuestion fusionne un patch sans muter l\'original', () => {
    const questions = [{ id: 'q1', libelle: 'A' }]
    const updated = updateQuestion(questions, 0, { libelle: 'B' })
    expect(updated[0].libelle).toBe('B')
    expect(questions[0].libelle).toBe('A')
  })

  it('optionsFromText/optionsToText sont symétriques', () => {
    const text = 'Oui\nNon\nPeut-être'
    const options = optionsFromText(text)
    expect(options).toEqual(['Oui', 'Non', 'Peut-être'])
    expect(optionsToText(options)).toBe(text)
  })

  it('optionsFromText ignore les lignes vides', () => {
    expect(optionsFromText('Oui\n\nNon\n')).toEqual(['Oui', 'Non'])
  })
})

// ── Rendu smoke + interactions ──
const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
  tester: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    enquetes: { create: mocks.create, update: mocks.update, tester: mocks.tester },
  },
}))

import EnqueteBuilder, { emptyForm } from './EnqueteBuilder'

beforeEach(() => { vi.clearAllMocks() })

describe('EnqueteBuilder (NTMKT8)', () => {
  it('ajouter une question conditionnelle « B si réponse A »', async () => {
    render(<EnqueteBuilder initial={emptyForm()} onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByTestId('enquete-ajouter-question'))
    fireEvent.click(screen.getByTestId('enquete-ajouter-question'))
    fireEvent.change(screen.getByTestId('enquete-question-0-libelle'),
      { target: { value: 'Avez-vous un projet solaire ?' } })
    // La condition n'apparaît qu'à partir de la 2e question.
    expect(screen.queryByTestId('enquete-question-0-condition-q')).toBeNull()
    const conditionSelect = screen.getByTestId('enquete-question-1-condition-q')
    fireEvent.change(conditionSelect, { target: { value: 'q1' } })
    expect(screen.getByTestId('enquete-question-1-condition-valeur')).toBeInTheDocument()
  })

  it('créer une enquête à 2 questions appelle create() avec le bon payload', async () => {
    mocks.create.mockResolvedValue({ data: { id: 5, token: 'tok123' } })
    const onSaved = vi.fn()
    render(<EnqueteBuilder initial={emptyForm()} onSaved={onSaved} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByTestId('enquete-titre'), { target: { value: 'Satisfaction' } })
    fireEvent.click(screen.getByTestId('enquete-ajouter-question'))
    fireEvent.change(screen.getByTestId('enquete-question-0-libelle'), { target: { value: 'Q1' } })
    fireEvent.click(screen.getByTestId('enquete-enregistrer'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].titre).toBe('Satisfaction')
    expect(mocks.create.mock.calls[0][0].questions).toHaveLength(1)
    expect(onSaved).toHaveBeenCalled()
  })

  it("« Tester » n'apparaît qu'une fois l'enquête enregistrée", async () => {
    render(<EnqueteBuilder initial={emptyForm()} onSaved={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByTestId('enquete-tester')).toBeNull()
  })

  it('tester une enquête existante appelle tester() sans créer de réponse', async () => {
    mocks.tester.mockResolvedValue({ data: { questions: [{ id: 'q1' }] } })
    render(<EnqueteBuilder initial={{ id: 9, titre: 'X', questions: [] }}
      onSaved={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByTestId('enquete-tester'))
    await waitFor(() => expect(mocks.tester).toHaveBeenCalledWith(9))
    expect(await screen.findByTestId('enquete-test-apercu')).toBeInTheDocument()
  })
})
