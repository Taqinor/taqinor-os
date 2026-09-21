import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

/* WIR205 — écarter / réintégrer sont des ACTIONS SERVEUR. L'écran ne les
   propose que sur un obstacle DÉJÀ enregistré (id numérique), il EXIGE le
   motif que le serveur exige, et il n'invente aucun état : c'est le parent qui
   appelle `aoApi.obstacles.ecarter/reintegrer` et rend la réponse. */
const ENREGISTRE = {
  id: 41,
  repere: 'F',
  nature: 'edicule',
  designation: 'Local technique',
  provenance: 'MESURE',
  x0: 0,
  x1: 2,
  y0: 0,
  y1: 2,
}

const ENREGISTRE_ECARTE = {
  ...ENREGISTRE,
  id: 42,
  repere: 'G',
  provenance: 'ECARTE',
  decision: 'Déposé au lot couverture',
}

describe('ObstaclesList — écarter / réintégrer (WIR205)', () => {
  it('écarter EXIGE un motif et le transmet au serveur via le parent', async () => {
    const user = userEvent.setup()
    const onEcarter = vi.fn(async () => {})
    const { container } = render(
      <ObstaclesList obstacles={[ENREGISTRE]} onEcarter={onEcarter} />,
    )

    await user.click(container.querySelector('[data-ao-ecarter="F"]'))
    const confirmer = container.querySelector('[data-ao-ecarter-confirmer="F"]')
    expect(confirmer).toBeDisabled() // pas de motif → pas d'écartement

    await user.type(
      screen.getByLabelText("Motif de l'écartement"),
      'Déposé au lot couverture — constaté sur site.',
    )
    expect(confirmer).toBeEnabled()
    await user.click(confirmer)

    expect(onEcarter).toHaveBeenCalledTimes(1)
    expect(onEcarter.mock.calls[0][0].id).toBe(41)
    expect(onEcarter.mock.calls[0][1]).toMatch(/Déposé au lot couverture/)
  })

  it('un obstacle pas encore enregistré ne peut pas être écarté (id local)', () => {
    const { container } = render(<ObstaclesList obstacles={[...MESURES]} />)
    const bouton = container.querySelector('[data-ao-ecarter="A"]')
    expect(bouton).toBeDisabled()
    expect(bouton.getAttribute('title')).toMatch(/pas encore enregistré/)
  })

  it('un obstacle écarté propose la RÉINTÉGRATION, et le refus serveur est écrit', async () => {
    const user = userEvent.setup()
    const onReintegrer = vi.fn(async () => {
      throw new Error('Le serveur a refusé la réintégration.')
    })
    const { container } = render(
      <ObstaclesList obstacles={[ENREGISTRE_ECARTE]} onReintegrer={onReintegrer} />,
    )

    expect(container.querySelector('[data-ao-ecarter="G"]')).toBeNull()
    await user.click(container.querySelector('[data-ao-reintegrer="G"]'))
    expect(onReintegrer).toHaveBeenCalledTimes(1)

    const erreur = await waitFor(() => {
      const el = container.querySelector('[data-ao-obstacles-erreur]')
      expect(el).toBeTruthy()
      return el
    })
    expect(erreur.textContent).toMatch(/refusé la réintégration/)
  })
})
