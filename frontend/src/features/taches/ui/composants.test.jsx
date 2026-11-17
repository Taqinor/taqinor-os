import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import CoquilleTaches from '../coquille/CoquilleTaches'
import BarreSelection from './BarreSelection'
import BoutonCopilote, { PHRASE_HORS_LIGNE, PHRASE_SANS_CLE } from './BoutonCopilote'
import FeuilleACrans from './FeuilleACrans'
import SelecteurProjet from './SelecteurProjet'

/* TCH45 — FeuilleACrans (crans 50 / 85 %, clavier ouvert), SelecteurProjet (« Nouveau projet »
   fixe), BarreSelection (lot), BoutonCopilote (`taqinor:assistant:ouvrir`, une phrase sans clé
   ou hors ligne). Tous montés dans la coquille : atteignables par toute route /taches/*. */

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
  delete window.visualViewport
})

const projets = [
  ...exempleContrat('taches', 'projets_liste').results,
  { id: 4, nom: 'Étude Salé', couleur: 'bleu', priorite: 2 },
  { id: 5, nom: 'Chantier Benali', couleur: 'ambre', priorite: 3 },
]

describe('TCH45 — FeuilleACrans', () => {
  const feuille = (props = {}) => render(
    <div className="tch">
      <button type="button">ouvreur</button>
      <FeuilleACrans ouverte titre="Quand" onFermer={() => {}} {...props}><button type="button">Aujourd'hui</button></FeuilleACrans>
    </div>,
  )

  it('est fermée tant que `ouverte` est faux', () => {
    render(<FeuilleACrans ouverte={false} titre="Quand" onFermer={() => {}} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('crans 50 % puis 85 % : la poignée bascule et change de nom', async () => {
    const user = userEvent.setup()
    feuille()
    const dialogue = screen.getByRole('dialog', { name: 'Quand' })
    expect(dialogue).toHaveClass('cran-50')
    await user.click(screen.getByRole('button', { name: 'Agrandir la feuille' }))
    expect(dialogue).toHaveClass('cran-85')
    expect(dialogue).not.toHaveClass('cran-50')
    await user.click(screen.getByRole('button', { name: 'Réduire la feuille' }))
    expect(dialogue).toHaveClass('cran-50')
  })

  it('peut s\'ouvrir directement à 85 %', () => {
    feuille({ cranInitial: '85' })
    expect(screen.getByRole('dialog')).toHaveClass('cran-85')
  })

  it('clavier ouvert : la feuille épouse son contenu SUR le clavier, les crans ne valent plus', async () => {
    const ecouteurs = {}
    window.visualViewport = {
      height: 500,
      offsetTop: 0,
      addEventListener: (type, fn) => { ecouteurs[type] = fn },
      removeEventListener: () => {},
    }
    vi.stubGlobal('innerHeight', 844)
    feuille()
    const dialogue = screen.getByRole('dialog')
    expect(dialogue).toHaveClass('sur-clavier')
    expect(dialogue).not.toHaveClass('cran-50')
    expect(dialogue.style.getPropertyValue('--tch-clavier-h')).toBe('344px')
    // le clavier se ferme : retour au cran
    window.visualViewport.height = 844
    await act(async () => { ecouteurs.resize() })
    expect(dialogue).toHaveClass('cran-50')
    expect(dialogue).not.toHaveClass('sur-clavier')
    vi.unstubAllGlobals()
  })

  it('Échap ferme, le focus est piégé et revient à l\'ouvreur', async () => {
    const onFermer = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <div className="tch">
        <button type="button">ouvreur</button>
        <FeuilleACrans ouverte={false} titre="Quand" onFermer={onFermer}><button type="button">Aujourd'hui</button></FeuilleACrans>
      </div>,
    )
    screen.getByRole('button', { name: 'ouvreur' }).focus()
    rerender(
      <div className="tch">
        <button type="button">ouvreur</button>
        <FeuilleACrans ouverte titre="Quand" onFermer={onFermer}><button type="button">Aujourd'hui</button></FeuilleACrans>
      </div>,
    )
    const dialogue = screen.getByRole('dialog')
    expect(dialogue.contains(document.activeElement)).toBe(true)
    // Tab en boucle : jamais hors de la feuille
    for (let i = 0; i < 6; i += 1) {
      await user.tab()
      expect(dialogue.contains(document.activeElement)).toBe(true)
    }
    await user.keyboard('{Escape}')
    expect(onFermer).toHaveBeenCalledTimes(1)
    rerender(
      <div className="tch">
        <button type="button">ouvreur</button>
        <FeuilleACrans ouverte={false} titre="Quand" onFermer={onFermer} />
      </div>,
    )
    expect(screen.getByRole('button', { name: 'ouvreur' })).toHaveFocus()
  })
})

describe('TCH45 — SelecteurProjet', () => {
  it('liste les projets, filtre sans accents ni casse, et garde « Nouveau projet » fixe', async () => {
    const user = userEvent.setup()
    render(<SelecteurProjet projets={projets} />)
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Ventes', 'Étude Salé', 'Chantier Benali'])
    await user.type(screen.getByRole('combobox', { name: 'Chercher un projet' }), 'etude')
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Étude Salé', 'Créer « etude »'])
    // aucun résultat : le bouton fixe reste
    await user.clear(screen.getByRole('combobox'))
    await user.type(screen.getByRole('combobox'), 'zzz')
    expect(screen.getByRole('button', { name: 'Nouveau projet' })).toBeInTheDocument()
  })

  it('Entrée choisit l\'option active, les flèches la déplacent', async () => {
    const onChoisir = vi.fn()
    const user = userEvent.setup()
    render(<SelecteurProjet projets={projets} valeur={3} onChoisir={onChoisir} />)
    expect(screen.getByRole('option', { name: 'Ventes' })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('combobox'))
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(onChoisir).toHaveBeenCalledWith(5)
  })

  it('« Nouveau projet » et « Créer « X » » rendent le nom tapé ; « Sans projet » rend null', async () => {
    const onNouveau = vi.fn()
    const onChoisir = vi.fn()
    const user = userEvent.setup()
    render(<SelecteurProjet projets={projets} sansProjet onNouveau={onNouveau} onChoisir={onChoisir} />)
    await user.click(screen.getByRole('option', { name: 'Sans projet' }))
    expect(onChoisir).toHaveBeenCalledWith(null)
    await user.type(screen.getByRole('combobox'), 'Site web')
    await user.click(screen.getByRole('option', { name: 'Créer « Site web »' }))
    expect(onNouveau).toHaveBeenLastCalledWith('Site web')
    await user.click(screen.getByRole('button', { name: 'Nouveau projet' }))
    expect(onNouveau).toHaveBeenLastCalledWith('Site web')
  })

  it('le point de couleur précède toujours le nom (la couleur n\'est jamais seule)', () => {
    render(<SelecteurProjet projets={projets} />)
    const option = screen.getByRole('option', { name: 'Ventes' })
    expect(option).toHaveAttribute('data-p', 'vert')
    expect(option.firstElementChild).toHaveClass('point')
  })
})

describe('TCH45 — BarreSelection', () => {
  it('annonce le nombre (singulier, pluriel) et déclenche les actions de lot', async () => {
    const onAction = vi.fn()
    const onFermer = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(<BarreSelection n={1} onAction={onAction} onFermer={onFermer} />)
    expect(screen.getByRole('status')).toHaveTextContent('1 sélectionnée')
    rerender(<BarreSelection n={3} onAction={onAction} onFermer={onFermer} />)
    expect(screen.getByRole('status')).toHaveTextContent('3 sélectionnées')
    const barre = screen.getByRole('toolbar', { name: 'Actions sur la sélection' })
    expect(within(barre).getAllByRole('button').map((b) => b.textContent || b.getAttribute('aria-label')))
      .toEqual(['Déplacer', 'Quand', 'Priorité', 'Terminer', 'Supprimer', 'Annuler la sélection'])
    await user.click(within(barre).getByRole('button', { name: 'Déplacer' }))
    expect(onAction).toHaveBeenCalledWith('deplacer')
    await user.click(within(barre).getByRole('button', { name: 'Annuler la sélection' }))
    expect(onFermer).toHaveBeenCalledTimes(1)
  })

  it('n\'existe pas à zéro', () => {
    const { container } = render(<BarreSelection n={0} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('TCH45 — BoutonCopilote', () => {
  it('ouvre le Copilote par l\'événement, avec l\'écran et la demande', async () => {
    const recu = vi.fn()
    window.addEventListener('taqinor:assistant:ouvrir', recu)
    render(<BoutonCopilote ecran="/taches/aujourdhui" question="Planifie ma journée" envoyer />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Copilote' }))
    window.removeEventListener('taqinor:assistant:ouvrir', recu)
    expect(recu).toHaveBeenCalledTimes(1)
    expect(recu.mock.calls[0][0].detail).toEqual({ ecran: '/taches/aujourdhui', question: 'Planifie ma journée', envoyer: true })
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('sans clé d\'IA : il ouvre quand même (les 4 demandes marchent) et dit la phrase', async () => {
    const recu = vi.fn()
    window.addEventListener('taqinor:assistant:ouvrir', recu)
    render(<BoutonCopilote ecran="/taches/aujourdhui" libre={false} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Copilote' }))
    window.removeEventListener('taqinor:assistant:ouvrir', recu)
    expect(recu).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).toHaveTextContent(PHRASE_SANS_CLE)
    expect(PHRASE_SANS_CLE).toBe("La conversation libre n'est pas branchée sur ce serveur. Les quatre demandes ci-dessus marchent sans elle.")
  })

  it('hors ligne : rien ne s\'ouvre, la phrase explique ; elle part d\'elle-même', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    const recu = vi.fn()
    window.addEventListener('taqinor:assistant:ouvrir', recu)
    render(<BoutonCopilote ecran="/taches/aujourdhui" />)
    fireEvent.click(screen.getByRole('button', { name: 'Copilote' }))
    window.removeEventListener('taqinor:assistant:ouvrir', recu)
    expect(recu).not.toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent(PHRASE_HORS_LIGNE)
    expect(PHRASE_HORS_LIGNE).toBe('Le Copilote a besoin du réseau. Ajouter, cocher et reporter marchent hors ligne.')
    await act(async () => { vi.advanceTimersByTime(8100) })
    expect(screen.queryByRole('status')).toBeNull()
  })
})

describe('TCH45 — montés dans la coquille', () => {
  const coquille = (props = {}) => render(
    <MemoryRouter initialEntries={['/taches/agenda']}>
      <CoquilleTaches ecran="agenda" titre="Agenda" {...props} />
    </MemoryRouter>,
  )

  it('le bouton Copilote est dans l\'en-tête de toute page', () => {
    coquille()
    expect(screen.getByRole('button', { name: 'Copilote' })).toBeInTheDocument()
  })

  it('une feuille, le sélecteur de projet et la barre de sélection se montent par prop', () => {
    coquille({
      feuille: { ouverte: true, titre: 'Quand', onFermer: () => {}, children: <p>contenu</p> },
      selecteurProjet: { ouverte: true, titre: 'Déplacer', projets, onChoisir: () => {}, onNouveau: () => {}, onFermer: () => {} },
      selection: { n: 2, onAction: () => {}, onFermer: () => {} },
    })
    expect(screen.getByRole('dialog', { name: 'Quand' })).toHaveTextContent('contenu')
    const selecteur = screen.getByRole('dialog', { name: 'Déplacer' })
    expect(within(selecteur).getByRole('button', { name: 'Nouveau projet' })).toBeInTheDocument()
    expect(screen.getByRole('toolbar')).toBeInTheDocument()
    // la barre de sélection remplace le bouton flottant
    expect(document.querySelector('.fab')).toBeNull()
  })

  it('sans sélection, le bouton flottant « Ajouter une tâche » est là', () => {
    coquille()
    expect(document.querySelectorAll('.fab')).toHaveLength(1)
  })
})
