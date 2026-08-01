import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuestionFiche, { deltaReel } from './QuestionFiche'

/* AOF107 (1/3) — le « Done = » exige :
   1. une question SANS impact chiffré est REFUSÉE avec le message qui
      explicite la règle ;
   2. le delta RÉEL (`compte_apres_modules` − `compte_avant_modules`) est
      affiché et historisé, comparé au prévisionnel. */

const QUESTION_BASE = {
  id: 42,
  repere: 'F',
  texte: 'Le grand rectangle non coté est-il confirmé néant ?',
  impact_min_modules: null,
  impact_max_modules: null,
  reponse: '',
  decision: '',
  date_decision: null,
  statut: 'posee',
}

describe('QuestionFiche — refus d’une question sans impact chiffré', () => {
  it('affiche le refus et désactive « Enregistrer la question » tant qu’aucun impact n’est chiffré', () => {
    render(<QuestionFiche question={QUESTION_BASE} onChange={() => {}} />)
    expect(screen.getByRole('alert').textContent).toMatch(
      /on ne pose une question que si sa réponse change le compte/,
    )
    expect(screen.getByRole('button', { name: 'Enregistrer la question' })).toBeDisabled()
  })

  it('autorise l’enregistrement dès qu’un impact minimal OU maximal est saisi', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<QuestionFiche question={QUESTION_BASE} onChange={onChange} />)
    await user.type(screen.getByLabelText('Impact minimal (modules)'), '8')
    expect(screen.getByRole('button', { name: 'Enregistrer la question' })).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Enregistrer la question' }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ impact_min_modules: 8 }))
  })
})

describe('QuestionFiche — delta RÉEL vs prévu', () => {
  it('affiche l’impact prévu (deux côtés) puis le delta réel après recalcul', () => {
    const { container } = render(
      <QuestionFiche
        question={{
          ...QUESTION_BASE,
          impact_min_modules: -2,
          impact_max_modules: 8,
          reponse: "L'emprise est bien néant.",
          compte_avant_modules: 512,
          compte_apres_modules: 520,
        }}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText(/-2 à \+8 modules/)).toBeInTheDocument()
    expect(container.querySelector('[data-ao-compte="8"]').textContent).toMatch(/Delta réel : \+8 module/)
  })

  it('`deltaReel` est une SOUSTRACTION D’AFFICHAGE entre deux comptes serveur', () => {
    expect(deltaReel({ compte_avant_modules: 512, compte_apres_modules: 522 })).toBe(10)
    expect(deltaReel({ compte_avant_modules: 512, compte_apres_modules: null })).toBeNull()
    expect(deltaReel({})).toBeNull()
  })

  it('le bouton « Recalculer » n’apparaît qu’après une réponse enregistrée', () => {
    const { rerender } = render(<QuestionFiche question={{ ...QUESTION_BASE, reponse: '' }} onChange={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Recalculer' })).not.toBeInTheDocument()
    rerender(<QuestionFiche question={{ ...QUESTION_BASE, reponse: 'Néant confirmé.' }} onChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Recalculer' })).toBeInTheDocument()
  })

  it('« Recalculer » relaie l’action au propriétaire de l’atelier, sans rejouer le calepinage lui-même', async () => {
    const user = userEvent.setup()
    const onRecalculer = vi.fn()
    render(
      <QuestionFiche
        question={{ ...QUESTION_BASE, reponse: 'Néant confirmé.' }}
        onChange={() => {}}
        onRecalculer={onRecalculer}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Recalculer' }))
    expect(onRecalculer).toHaveBeenCalledTimes(1)
  })
})

describe('QuestionFiche — historique des recalculs', () => {
  it('liste chaque recalcul avec son delta', () => {
    render(
      <QuestionFiche
        question={QUESTION_BASE}
        historique={[
          { date: '2026-07-28', compte_avant_modules: 512, compte_apres_modules: 522 },
          { date: '2026-07-29', compte_avant_modules: 522, compte_apres_modules: 562 },
        ]}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText(/delta \+10 module/)).toBeInTheDocument()
    expect(screen.getByText(/delta \+40 module/)).toBeInTheDocument()
  })
})

describe('QuestionFiche — cas dégénéré', () => {
  it('ne rend rien sans `question`', () => {
    const { container } = render(<QuestionFiche question={null} onChange={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
