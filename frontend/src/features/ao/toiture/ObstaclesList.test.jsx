import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ObstaclesList from './ObstaclesList'

/* AOF90 — ce que le test pur (`gardePublication.test.mjs`) ne peut pas prouver :
   que l'ÉCRAN bloque réellement, qu'il nomme les fautifs sous les yeux de
   l'utilisateur, et que le lien vers la création de question part bien d'ici. */

const MESURES = Array.from({ length: 3 }, (_, i) => ({
  id: `m${i}`,
  repere: String.fromCharCode(65 + i),
  nature: 'edicule',
  designation: `Édicule ${String.fromCharCode(65 + i)}`,
  provenance: 'MESURE',
  x0: 0,
  x1: 2,
  y0: 0,
  y1: 3,
}))

const SUR_PLAN = {
  id: 'p1',
  repere: 'D',
  nature: 'cage_escalier',
  designation: "Cage d'escalier",
  provenance: 'PLAN',
  x0: 0,
  x1: 4,
  y0: 0,
  y1: 5,
}

const ECARTE = {
  id: 'e1',
  repere: 'E',
  nature: 'cheminee',
  designation: 'Souche démolie',
  provenance: 'ECARTE',
  decision: 'Démolie au lot gros œuvre — confirmé par le MOA',
  x0: 0,
  x1: 1,
  y0: 0,
  y1: 1,
}

describe('ObstaclesList (AOF90)', () => {
  it('affiche le compteur en permanence, écartés comptés à part', () => {
    const { container } = render(<ObstaclesList obstacles={[...MESURES, ECARTE]} />)
    expect(container.querySelector('[data-ao-compte]').textContent).toBe(
      '3 obstacles — 3 mesurés, 0 à confirmer, 0 deviné (+ 1 écartés)',
    )
    expect(container.querySelector('[data-ao-compte]').dataset.aoCompte).toBe('3')
  })

  it('bloque la publication en NOMMANT le fautif et ouvre la question au client', async () => {
    const user = userEvent.setup()
    const onPoserQuestion = vi.fn()
    const { container } = render(
      <ObstaclesList obstacles={[...MESURES, SUR_PLAN]} onPoserQuestion={onPoserQuestion} />,
    )

    expect(container.querySelector('[data-ao-etat]').dataset.aoEtat).toBe('bloque')
    const bloc = screen.getByRole('alert')
    expect(bloc.textContent).toMatch(/Publication bloquée/)
    expect(bloc.textContent).toMatch(/D \(Cage d'escalier — relevé sur plan\)/)
    expect(
      screen.getByRole('button', { name: 'Marquer la toiture prête à publier' }),
    ).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Poser la question au client' }))
    const [question, fautifs] = onPoserQuestion.mock.calls[0]
    expect(question.reperes).toEqual(['D'])
    expect(question.corps).toMatch(/Cage d'escalier/)
    expect(fautifs.map((o) => o.id)).toEqual(['p1'])
  })

  it('un relevé entièrement mesuré redevient publiable', async () => {
    const user = userEvent.setup()
    const onPretAPublier = vi.fn()
    const { container } = render(
      <ObstaclesList obstacles={MESURES} onPretAPublier={onPretAPublier} />,
    )
    expect(container.querySelector('[data-ao-etat]').dataset.aoEtat).toBe('publiable')
    expect(screen.queryByRole('button', { name: 'Poser la question au client' })).toBeNull()
    await user.click(
      screen.getByRole('button', { name: 'Marquer la toiture prête à publier' }),
    )
    expect(onPretAPublier).toHaveBeenCalled()
  })

  it("le survol d'une ligne remonte au canvas, et l'écarté se masque à la demande", async () => {
    const user = userEvent.setup()
    const onSurvol = vi.fn()
    const { container } = render(
      <ObstaclesList obstacles={[...MESURES, ECARTE]} survolId="e1" onSurvol={onSurvol} />,
    )

    // Synchronisation inverse : le survol venu du canvas allume la ligne.
    expect(container.querySelector('[data-ao-survole="oui"]').dataset.aoRepere).toBe('E')
    // L'écarté est listé AVEC sa décision, par défaut.
    expect(screen.getByText(/Démolie au lot gros œuvre/)).toBeTruthy()

    await user.hover(container.querySelector('[data-ao-repere="A"]'))
    expect(onSurvol).toHaveBeenCalledWith('m0')

    await user.click(screen.getByLabelText(/Afficher les écartés/))
    expect(container.querySelectorAll('tbody tr')).toHaveLength(3)
    expect(screen.queryByText(/Démolie au lot gros œuvre/)).toBeNull()
  })
})
