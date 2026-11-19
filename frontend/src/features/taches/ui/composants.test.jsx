import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  MemoryRouter, useLocation, useNavigationType, useSearchParams,
} from 'react-router-dom'
import { useLayoutEffect, useRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import CoquilleTaches from '../coquille/CoquilleTaches'
import { useClavierListe } from '../lib/clavierListe'
import { useOuvrirFiche } from '../lib/fiche'
import { FeuilleAttente } from './ActionsLigne'
import BarreSelection from './BarreSelection'
import BoutonCopilote, { PHRASE_HORS_LIGNE, PHRASE_SANS_CLE } from './BoutonCopilote'
import FeuilleACrans, { naviguerApresFeuille } from './FeuilleACrans'
import SelecteurProjet from './SelecteurProjet'
import SelecteurQuand from './SelecteurQuand'

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

  it('passe visuelle n° 26 — le focus posé d\'office sur la poignée ne dessine pas d\'anneau ; une action désignée garde le sien', () => {
    const focus = vi.spyOn(HTMLElement.prototype, 'focus')
    const { unmount } = feuille()
    const poignee = screen.getByRole('button', { name: 'Agrandir la feuille' })
    expect(poignee).toHaveFocus()
    expect(focus.mock.contexts.at(-1)).toBe(poignee)
    expect(focus.mock.calls.at(-1)).toEqual([{ focusVisible: false }])
    unmount()
    focus.mockClear()
    fireEvent.keyDown(document.body, { key: 'Tab' }) // ouverte au clavier
    const auClavier = render(
      <FeuilleACrans ouverte titre="Quand" onFermer={() => {}}><button type="button" data-focus-initial>OK</button></FeuilleACrans>,
    )
    expect(screen.getByRole('button', { name: 'OK' })).toHaveFocus()
    expect(focus.mock.calls.at(-1)).toEqual([])
    auClavier.unmount()
    // R3-064 — ouverte à la souris (bilan, Alléger : le × est le premier focalisable) : aucun anneau
    focus.mockClear()
    fireEvent.pointerDown(document.body)
    const style = document.createElement('style')
    style.textContent = '.poignee { display: none; }'
    document.head.appendChild(style)
    try {
      render(<FeuilleACrans ouverte titre="Bilan du soir" onFermer={() => {}}><button type="button">Valider</button></FeuilleACrans>)
      expect(screen.getByRole('button', { name: 'Fermer' })).toHaveFocus()
      expect(focus.mock.calls.at(-1)).toEqual([{ focusVisible: false }])
    } finally {
      style.remove()
    }
    focus.mockRestore()
  })

  it('R2-048 — un contenu court : la feuille épouse son contenu (`cran-auto`, plafond 85 %) au lieu de laisser du blanc', () => {
    const hauteurs = (feuilleH, corpsClient, corpsScroll) => {
      vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(function h() { return this.classList.contains('feuille') ? feuilleH : 0 })
      vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function h() { return this.classList.contains('feuille-corps') ? corpsClient : 0 })
      vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(function h() { return this.classList.contains('feuille-corps') ? corpsScroll : 0 })
    }
    vi.stubGlobal('innerHeight', 844)
    // feuille à 85 % (717 px), contenu de 260 px : 717 − 600 + 260 = 377 px suffisent
    hauteurs(717, 600, 260)
    const { unmount } = render(<div className="tch"><FeuilleACrans ouverte titre="Alléger ma journée" cranInitial="85" onFermer={() => {}}><p>court</p></FeuilleACrans></div>)
    expect(screen.getByRole('dialog')).toHaveClass('cran-auto')
    expect(screen.getByRole('dialog')).not.toHaveClass('cran-85')
    unmount()
    vi.restoreAllMocks()
    // contenu plus haut que le cran : le cran reste (le corps défile)
    hauteurs(422, 300, 900)
    render(<div className="tch"><FeuilleACrans ouverte titre="Quand" onFermer={() => {}}><p>long</p></FeuilleACrans></div>)
    expect(screen.getByRole('dialog')).toHaveClass('cran-50')
    vi.unstubAllGlobals()
  })

  it('R3-066 — un champ `autoFocus` (Renommer, Nouveau projet) GARDE le curseur ; fermée, le focus revient à l\'ouvreur', () => {
    const page = (ouverte) => (
      <div className="tch">
        <button type="button">Renommer le projet</button>
        {ouverte ? (
          <FeuilleACrans ouverte titre="Renommer" onFermer={() => {}}>
            <input aria-label="Nom" autoFocus defaultValue="Site web" />
          </FeuilleACrans>
        ) : null}
      </div>
    )
    const { rerender } = render(page(false))
    const ouvreur = screen.getByRole('button', { name: 'Renommer le projet' })
    act(() => { ouvreur.focus() })
    rerender(page(true))
    expect(screen.getByRole('textbox', { name: 'Nom' })).toHaveFocus() // pas la poignée « Agrandir la feuille »
    // iPhone : le menu ⋯ qui a ouvert « Renommer » rend le focus à son bouton juste APRÈS : le champ le reprend
    act(() => { ouvreur.focus() })
    expect(screen.getByRole('textbox', { name: 'Nom' })).toHaveFocus()
    rerender(page(false))
    expect(ouvreur).toHaveFocus()
  })

  it('R3-066 — iPhone, ouverte depuis le menu ⋯ (Radix) : le menu reprend le focus au champ `autoFocus` dès le montage, puis le rend à son bouton ; le champ le récupère, jamais la poignée', () => {
    function MenuQuiReprend() {
      // ce que fait le FocusScope du menu Radix encore ouvert : il ramène le focus chez lui, au montage même
      useLayoutEffect(() => { document.getElementById('item-renommer')?.focus() }, [])
      return null
    }
    const page = (ouverte, menu) => (
      <div className="tch">
        <button type="button">Plus d'actions</button>
        {menu ? <div role="menu"><button type="button" id="item-renommer">Renommer</button></div> : null}
        {ouverte ? (
          <FeuilleACrans ouverte titre="Renommer" onFermer={() => {}}>
            <input aria-label="Nom" autoFocus defaultValue="Site web" />
            <MenuQuiReprend />
          </FeuilleACrans>
        ) : null}
      </div>
    )
    const { rerender } = render(page(false, true))
    const bouton = screen.getByRole('button', { name: "Plus d'actions" })
    rerender(page(true, true))
    expect(screen.getByRole('button', { name: 'Renommer' })).toHaveFocus() // le menu le tient encore
    rerender(page(true, false)) // le menu se referme…
    act(() => { bouton.focus() }) // … et rend le focus à son bouton
    expect(screen.getByRole('textbox', { name: 'Nom' })).toHaveFocus()
  })

  it('R3-066 — … et quand le menu REFUSE le focus au champ dès sa sortie (FocusScope Radix : `focusout` qui le reprend), le champ n\'a jamais eu le focus : la feuille le retrouve quand même', () => {
    function Menu() {
      const ref = useRef(null)
      useLayoutEffect(() => { ref.current.querySelector('button').focus() }, [])
      return <div role="menu" ref={ref}><button type="button">Renommer</button></div>
    }
    // ce que Chrome fait (relevé sur l'écran réel, debug-renommer.cjs) : la sortie du menu est annoncée (`focusout`, vers
    // le champ), le FocusScope la refuse et le champ ne reçoit JAMAIS `focusin` — jsdom, lui, focaliserait quand même
    const focusReel = HTMLElement.prototype.focus
    vi.spyOn(HTMLElement.prototype, 'focus').mockImplementation(function focusRefuse(...args) {
      const item = document.querySelector('[role="menu"] button')
      if (this.tagName === 'INPUT' && item) {
        item.dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: this }))
        return undefined
      }
      return focusReel.apply(this, args)
    })
    const page = (ouverte, menu) => (
      <div className="tch">
        <button type="button">Plus d'actions</button>
        {menu ? <Menu /> : null}
        {ouverte ? (
          <FeuilleACrans ouverte titre="Renommer" onFermer={() => {}}><input aria-label="Nom" autoFocus defaultValue="Site web" /></FeuilleACrans>
        ) : null}
      </div>
    )
    const { rerender } = render(page(false, true))
    const bouton = screen.getByRole('button', { name: "Plus d'actions" })
    expect(screen.getByRole('button', { name: 'Renommer' })).toHaveFocus()
    rerender(page(true, true))
    expect(screen.getByRole('textbox', { name: 'Nom' })).not.toHaveFocus() // le menu l'a gardé
    rerender(page(true, false))
    act(() => { bouton.focus() })
    expect(screen.getByRole('textbox', { name: 'Nom' })).toHaveFocus()
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

  it('R2-043 — poignée cachée (bureau) : le focus va au premier champ VISIBLE, sinon à « Fermer » ; jamais derrière', () => {
    const style = document.createElement('style')
    style.textContent = '.poignee { display: none; }'
    document.head.appendChild(style)
    try {
      const { unmount } = render(
        <div className="tch">
          <button type="button">ouvreur</button>
          <FeuilleACrans ouverte titre="Fiche" onFermer={() => {}}><button type="button">Quand</button><input aria-label="Titre" /></FeuilleACrans>
        </div>,
      )
      expect(screen.getByRole('textbox', { name: 'Titre' })).toHaveFocus()
      unmount()
      render(<FeuilleACrans ouverte titre="Supprimer" onFermer={() => {}}><button type="button">Supprimer</button></FeuilleACrans>)
      expect(screen.getByRole('button', { name: 'Fermer' })).toHaveFocus()
    } finally {
      style.remove()
    }
  })

  it('R2-043 — un menu qui rend le focus à son bouton APRÈS l\'ouverture ne le garde pas derrière la feuille ; il y revient à la fermeture', () => {
    const page = (ouverte) => (
      <div className="tch">
        <button type="button">Plus d'actions</button>
        <FeuilleACrans ouverte={ouverte} titre="Alléger ma journée" onFermer={() => {}}><button type="button">Garder</button></FeuilleACrans>
      </div>
    )
    const { rerender } = render(page(true))
    const dialogue = screen.getByRole('dialog', { name: 'Alléger ma journée' })
    expect(dialogue.contains(document.activeElement)).toBe(true)
    // ce que fait le menu Radix en se refermant : le focus repart sur son déclencheur, derrière la feuille
    act(() => { screen.getByRole('button', { name: "Plus d'actions" }).focus() })
    expect(dialogue.contains(document.activeElement)).toBe(true)
    rerender(page(false))
    expect(screen.getByRole('button', { name: "Plus d'actions" })).toHaveFocus()
  })

  it('R2-050 — `variante="panneau"` au bureau large : panneau à droite NON modal (sans voile), le focus reste à la ligne, Échap ferme', async () => {
    vi.stubGlobal('matchMedia', (q) => ({ matches: q === '(min-width: 1024px)', media: q, addEventListener: () => {}, removeEventListener: () => {} }))
    const onFermer = vi.fn()
    const user = userEvent.setup()
    const page = (ouverte) => (
      <div className="tch">
        <div data-ligne="tache:21"><button type="button">Ligne suivante</button></div>
        <div data-ligne="tache:20"><button type="button">Ligne ouverte</button></div>
        <FeuilleACrans ouverte={ouverte} variante="panneau" titre="Fiche" onFermer={onFermer}><input aria-label="Titre" /></FeuilleACrans>
      </div>
    )
    const { container, rerender } = render(page(false))
    screen.getByRole('button', { name: 'Ligne ouverte' }).focus()
    rerender(page(true))
    const panneau = screen.getByRole('dialog', { name: 'Fiche' })
    expect(panneau).toHaveClass('panneau-bureau')
    expect(panneau).toHaveAttribute('aria-modal', 'false')
    expect(container.querySelector('.voile')).toBeNull()
    expect(screen.getByRole('button', { name: 'Ligne ouverte' })).toHaveFocus()
    // la liste reste à la main : le focus peut aller sur une autre ligne sans être ramené dans le panneau
    act(() => { screen.getByRole('button', { name: 'Ligne suivante' }).focus() })
    expect(screen.getByRole('button', { name: 'Ligne suivante' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(onFermer).toHaveBeenCalledTimes(1)
    rerender(page(false))
    expect(screen.getByRole('button', { name: 'Ligne suivante' })).toHaveFocus() // jamais ramené en arrière
    vi.unstubAllGlobals()
  })

  it('R2-050 — un panneau ouvert depuis un MENU (pas une ligne) prend le focus, même quand le menu le rend à son bouton', () => {
    vi.stubGlobal('matchMedia', (q) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }))
    render(
      <div className="tch">
        <button type="button">Plus d'actions</button>
        <FeuilleACrans ouverte variante="panneau" titre="Bilan du soir" onFermer={() => {}}><button type="button">Valider</button></FeuilleACrans>
      </div>,
    )
    const panneau = screen.getByRole('dialog', { name: 'Bilan du soir' })
    expect(panneau.contains(document.activeElement)).toBe(true)
    act(() => { screen.getByRole('button', { name: "Plus d'actions" }).focus() }) // le menu Radix rend le focus
    expect(panneau.contains(document.activeElement)).toBe(true)
    vi.unstubAllGlobals()
  })

  it('R2-050 — sous 1024 px, `variante="panneau"` reste un dialogue modal (iPhone : feuille du bas)', () => {
    vi.stubGlobal('matchMedia', (q) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }))
    const { container } = render(<div className="tch"><FeuilleACrans ouverte variante="panneau" titre="Fiche" onFermer={() => {}}><p>x</p></FeuilleACrans></div>)
    expect(screen.getByRole('dialog', { name: 'Fiche' })).toHaveClass('dialogue-bureau')
    expect(screen.getByRole('dialog', { name: 'Fiche' })).toHaveAttribute('aria-modal', 'true')
    expect(container.querySelector('.voile')).not.toBeNull()
    vi.unstubAllGlobals()
  })

  it('R2-049 — ouverte au doigt, la feuille rend le focus SANS anneau ; ouverte au clavier, avec', () => {
    const page = (ouverte) => (
      <div className="tch">
        <button type="button">Plus d'actions</button>
        <FeuilleACrans ouverte={ouverte} titre="Alléger ma journée" onFermer={() => {}}><button type="button">Garder</button></FeuilleACrans>
      </div>
    )
    const { rerender } = render(page(false))
    const ouvreur = screen.getByRole('button', { name: "Plus d'actions" })
    ouvreur.focus()
    fireEvent.pointerDown(ouvreur)
    rerender(page(true))
    const focus = vi.spyOn(HTMLElement.prototype, 'focus')
    rerender(page(false))
    expect(ouvreur).toHaveFocus()
    expect(focus.mock.contexts.at(-1)).toBe(ouvreur)
    expect(focus.mock.calls.at(-1)).toEqual([{ focusVisible: false }])
    focus.mockClear()
    ouvreur.focus()
    fireEvent.keyDown(ouvreur, { key: 'Enter' })
    rerender(page(true))
    rerender(page(false))
    expect(focus.mock.contexts.at(-1)).toBe(ouvreur)
    expect(focus.mock.calls.at(-1)).toEqual([])
    focus.mockRestore()
  })

  describe('vague 2 — la SORTIE : une copie inerte s\'efface, le focus revient tout de suite', () => {
    const mouvement = (permis) => vi.stubGlobal('matchMedia', (q) => ({
      matches: permis && q === '(prefers-reduced-motion: no-preference)', media: q, addEventListener() {}, removeEventListener() {},
    }))
    afterEach(() => { vi.unstubAllGlobals() })
    const page = (ouverte) => (
      <div className="tch">
        <button type="button">ouvreur</button>
        <FeuilleACrans ouverte={ouverte} titre="Quand" onFermer={() => {}}><input aria-label="Jour" defaultValue="" /></FeuilleACrans>
      </div>
    )

    it('fermée : plus AUCUN dialogue, le focus est à l\'ouvreur ; la copie (sans rôle, inerte, valeur tapée) part à la fin de l\'animation', async () => {
      mouvement(true)
      const { container, rerender } = render(page(false))
      screen.getByRole('button', { name: 'ouvreur' }).focus()
      rerender(page(true))
      fireEvent.change(screen.getByRole('textbox', { name: 'Jour' }), { target: { value: 'jeudi' } })
      rerender(page(false))
      expect(screen.queryByRole('dialog')).toBeNull()
      expect(screen.getByRole('button', { name: 'ouvreur' })).toHaveFocus()
      await act(async () => { await Promise.resolve() })
      const copie = container.querySelector('.feuille.sortante')
      expect(copie).not.toBeNull()
      expect(container.querySelector('.voile.sortante')).not.toBeNull()
      expect(copie).toHaveAttribute('aria-hidden', 'true')
      expect(copie.inert).toBe(true)
      expect(copie.getAttribute('role')).toBeNull()
      expect(copie.querySelector('input').value).toBe('jeudi')
      fireEvent.animationEnd(copie)
      expect(container.querySelector('.sortante')).toBeNull()
    })

    it('démontée avec son écran (la fiche) : la copie garde ses ancêtres de classe, sans leurs data-*', async () => {
      mouvement(true)
      const ecran = (avecFiche) => (
        <div className="tch">
          {avecFiche ? <div className="fiche" data-fiche="12"><FeuilleACrans ouverte titre="Fiche" onFermer={() => {}}><p>x</p></FeuilleACrans></div> : null}
        </div>
      )
      const { container, rerender } = render(ecran(true))
      rerender(ecran(false))
      await act(async () => { await Promise.resolve() })
      const copie = container.querySelector('.tch > .fiche > .feuille.sortante')
      expect(copie).not.toBeNull()
      expect(container.querySelector('[data-fiche]')).toBeNull()
    })

    it('« Réduire les animations » : rien ne reste', async () => {
      mouvement(false)
      const { container, rerender } = render(page(true))
      rerender(page(false))
      await act(async () => { await Promise.resolve() })
      expect(container.querySelector('.sortante')).toBeNull()
    })
  })

  it('R2-043 — Échap ferme même quand le focus est DERRIÈRE la feuille ; seule la plus haute se ferme', async () => {
    const dessous = vi.fn()
    const dessus = vi.fn()
    const user = userEvent.setup()
    render(
      <div className="tch">
        <button type="button">derrière</button>
        <FeuilleACrans ouverte titre="Fiche" onFermer={dessous}><button type="button">a</button></FeuilleACrans>
        <FeuilleACrans ouverte titre="Quand" onFermer={dessus}><button type="button">b</button></FeuilleACrans>
      </div>,
    )
    screen.getByRole('button', { name: 'derrière' }).focus()
    await user.keyboard('{Escape}')
    expect(dessus).toHaveBeenCalledTimes(1)
    expect(dessous).not.toHaveBeenCalled()
  })

  it('Raccord F2 — le retour arrière du navigateur ferme la feuille (l\'écran reste) ; fermée autrement, l\'entrée est retirée', async () => {
    const onFermer = vi.fn()
    const pose = vi.spyOn(window.history, 'pushState')
    const retour = vi.spyOn(window.history, 'back')
    const { rerender } = render(<FeuilleACrans ouverte titre="Quand" onFermer={onFermer}><button type="button">x</button></FeuilleACrans>)
    await vi.waitFor(() => expect(pose).toHaveBeenCalledTimes(1))
    const marque = pose.mock.calls[0][0].tchFeuille
    expect(window.history.state?.tchFeuille).toBe(marque)
    // le geste « retour » de l'iPhone : l'entrée marquée part, la feuille se ferme
    act(() => { window.history.back() })
    await vi.waitFor(() => expect(onFermer).toHaveBeenCalledTimes(1))
    rerender(<FeuilleACrans ouverte={false} titre="Quand" onFermer={onFermer} />)
    expect(retour).toHaveBeenCalledTimes(1) // le nôtre seulement : fermée PAR le retour, rien à retirer de plus
    // fermée par la croix : l'entrée posée est retirée
    rerender(<FeuilleACrans ouverte titre="Quand" onFermer={onFermer}><button type="button">x</button></FeuilleACrans>)
    await vi.waitFor(() => expect(pose).toHaveBeenCalledTimes(2))
    rerender(<FeuilleACrans ouverte={false} titre="Quand" onFermer={onFermer} />)
    expect(retour).toHaveBeenCalledTimes(2)
  })

  it('F2 acceptation (P138.3) — une navigation voulue à la fermeture gagne : elle REMPLACE l\'entrée de la feuille, aucun retour arrière', async () => {
    const pose = vi.spyOn(window.history, 'pushState')
    const retour = vi.spyOn(window.history, 'back')
    const navigate = vi.fn()
    const { rerender } = render(<FeuilleACrans ouverte titre="Supprimer le projet" onFermer={() => {}}><button type="button">x</button></FeuilleACrans>)
    await vi.waitFor(() => expect(pose).toHaveBeenCalledTimes(1))
    // l'écran ferme sa feuille ET navigue dans le même geste (supprimer un projet → la liste)
    naviguerApresFeuille(navigate, '/taches/projets')
    rerender(<FeuilleACrans ouverte={false} titre="Supprimer le projet" onFermer={() => {}} />)
    expect(navigate).toHaveBeenCalledWith('/taches/projets', { replace: true })
    expect(retour).not.toHaveBeenCalled()
    // la fermeture suivante, sans navigation, retire de nouveau son entrée
    rerender(<FeuilleACrans ouverte titre="Quand" onFermer={() => {}}><button type="button">x</button></FeuilleACrans>)
    await vi.waitFor(() => expect(pose).toHaveBeenCalledTimes(2))
    rerender(<FeuilleACrans ouverte={false} titre="Quand" onFermer={() => {}} />)
    expect(retour).toHaveBeenCalledTimes(1)
  })

  it('F2 acceptation (P138.3) — sans feuille ouverte, naviguerApresFeuille navigue normalement (une entrée de plus)', () => {
    window.history.replaceState({}, '')
    const navigate = vi.fn()
    naviguerApresFeuille(navigate, '/taches/aujourdhui')
    expect(navigate).toHaveBeenCalledWith('/taches/aujourdhui', {})
  })

  it('R3-060 — fermer (Échap, croix, voile, retour arrière) quitte d\'abord le champ en cours : son `onBlur` enregistre AVANT `onFermer`', async () => {
    const ordre = []
    const onFermer = vi.fn(() => { ordre.push('fermer') })
    const { container } = render(
      <div className="tch">
        <FeuilleACrans ouverte titre="Quand" onFermer={onFermer}><input aria-label="Heure" onBlur={() => { ordre.push('blur') }} /></FeuilleACrans>
      </div>,
    )
    const champ = screen.getByLabelText('Heure')
    const fermerPar = async (geste) => {
      ordre.length = 0
      act(() => { champ.focus() })
      await geste()
      expect(ordre).toEqual(['blur', 'fermer'])
    }
    await fermerPar(() => { fireEvent.keyDown(champ, { key: 'Escape' }) })
    // iPhone : toucher un bouton ne lui donne pas le focus, le champ le gardait jusqu'au démontage
    await fermerPar(() => { fireEvent.click(screen.getByRole('button', { name: 'Fermer' })) })
    await fermerPar(() => { fireEvent.click(container.querySelector('.voile')) })
    await vi.waitFor(() => expect(window.history.state?.tchFeuille).toBeTruthy())
    await fermerPar(async () => {
      act(() => { window.history.back() })
      await vi.waitFor(() => expect(ordre).toContain('fermer'))
    })
  })

  it('R3-063 — `apresFermeture` part une fois l\'entrée d\'historique de la feuille RETIRÉE : la feuille suivante pose la sienne sans être fermée par ce retour', async () => {
    const pose = vi.spyOn(window.history, 'pushState')
    const apres = vi.fn(() => window.history.state?.tchFeuille ?? null)
    const page = (ouverte) => <FeuilleACrans ouverte={ouverte} titre="Devis Settat" onFermer={() => {}} apresFermeture={apres}><button type="button">x</button></FeuilleACrans>
    const { rerender } = render(page(true))
    await vi.waitFor(() => expect(pose).toHaveBeenCalledTimes(1))
    rerender(page(false))
    expect(apres).not.toHaveBeenCalled() // le retour arrière est en route
    await vi.waitFor(() => expect(apres).toHaveBeenCalledTimes(1))
    expect(apres.mock.results[0].value).toBeNull() // appelée APRÈS le retour : l'entrée de la feuille n'est plus là
    // fermée avant d'avoir posé son entrée : tout de suite
    apres.mockClear()
    rerender(page(true))
    rerender(page(false))
    expect(apres).toHaveBeenCalledTimes(1)
  })

  describe('R4-20 — une feuille se TIRE vers le bas : elle suit le doigt, se ferme au-delà d\'un seuil, revient sinon', () => {
    // jsdom ne mesure rien : la feuille vaut la moitié de l'écran (384 px), le seuil 30 % ≈ 115 px
    const toucher = (cible, type, y, x = 200) => {
      const points = type === 'touchEnd' || type === 'touchCancel' ? [] : [{ clientX: x, clientY: y, identifier: 1 }]
      fireEvent[type](cible, { touches: points, changedTouches: [{ clientX: x, clientY: y, identifier: 1 }] })
    }
    /** Un glissé de `dy` px en `pas` étapes de 16 ms (horloge simulée : la vitesse se mesure). */
    const tirer = (depart, dy, { pas = 15, x = 200, finir = true } = {}) => {
      const y0 = 300
      toucher(depart, 'touchStart', y0, x)
      for (let i = 1; i <= pas; i += 1) {
        act(() => { vi.advanceTimersByTime(16) })
        toucher(depart, 'touchMove', y0 + (dy * i) / pas, x)
      }
      if (finir) toucher(depart, 'touchEnd', y0 + dy, x)
    }
    const monterFeuille = (props = {}, contenu = <button type="button">Aujourd&apos;hui</button>) => {
      const onFermer = vi.fn()
      const rendu = render(
        <div className="tch">
          <FeuilleACrans ouverte titre="Quand" onFermer={onFermer} {...props}>{contenu}</FeuilleACrans>
        </div>,
      )
      return { onFermer, dialogue: screen.getAllByRole('dialog', { name: 'Quand' }).at(-1), ...rendu }
    }

    it('pendant le geste la feuille suit le doigt ; 80 px puis lâché : elle revient, rien ne ferme', () => {
      vi.useFakeTimers()
      const { onFermer, dialogue } = monterFeuille()
      tirer(dialogue.querySelector('.poignee'), 80, { finir: false })
      expect(dialogue.style.transform).toBe('translateY(80px)')
      expect(dialogue).toHaveClass('tiree')
      toucher(dialogue.querySelector('.poignee'), 'touchEnd', 380)
      expect(onFermer).not.toHaveBeenCalled()
      expect(dialogue.style.transform).toBe('')
      expect(dialogue).not.toHaveClass('tiree')
    })

    it('300 px depuis la poignée, ou depuis l\'en-tête : elle se ferme (en quittant d\'abord le champ en cours, R3-060)', () => {
      vi.useFakeTimers()
      const ordre = []
      const { onFermer, dialogue } = monterFeuille({ onFermer: vi.fn(() => ordre.push('fermer')) },
        <input aria-label="Heure" onBlur={() => { ordre.push('blur') }} />)
      act(() => { screen.getByLabelText('Heure').focus() })
      tirer(dialogue.querySelector('.poignee'), 300)
      expect(ordre).toEqual(['blur', 'fermer'])
      expect(onFermer).not.toHaveBeenCalled() // la prop remplacée : c'est la nôtre qui compte
      const deux = monterFeuille({ titre: 'Quand' })
      tirer(deux.dialogue.querySelector('.feuille-titre'), 300)
      expect(deux.onFermer).toHaveBeenCalledTimes(1)
    })

    it('un jet rapide (60 px en 32 ms) ferme aussi ; un glissé vers le haut depuis la poignée passe au cran 85 %', () => {
      vi.useFakeTimers()
      const { onFermer, dialogue } = monterFeuille()
      tirer(dialogue.querySelector('.poignee'), 60, { pas: 2 })
      expect(onFermer).toHaveBeenCalledTimes(1)
      const haut = monterFeuille()
      const autre = haut.dialogue
      tirer(autre.querySelector('.poignee'), -80)
      expect(haut.onFermer).not.toHaveBeenCalled()
      expect(autre).toHaveClass('cran-85')
    })

    it('depuis le CONTENU : seulement quand il est défilé tout en haut ; défilé, le geste lui appartient (il défile, rien ne ferme)', () => {
      vi.useFakeTimers()
      const { onFermer, dialogue } = monterFeuille({}, <ul aria-label="Liste">{[1, 2, 3].map((n) => <li key={n}>Ligne {n}</li>)}</ul>)
      const corps = dialogue.querySelector('.feuille-corps')
      const ligne = screen.getByText('Ligne 2')
      Object.defineProperty(corps, 'scrollHeight', { configurable: true, value: 2000 })
      Object.defineProperty(corps, 'clientHeight', { configurable: true, value: 300 })
      corps.scrollTop = 120
      tirer(ligne, 300)
      expect(onFermer).not.toHaveBeenCalled()
      expect(dialogue.style.transform).toBe('')
      corps.scrollTop = 0
      tirer(ligne, 300)
      expect(onFermer).toHaveBeenCalledTimes(1)
    })

    it('un champ de texte, un glissé horizontal : jamais de geste de feuille', () => {
      vi.useFakeTimers()
      const { onFermer, dialogue } = monterFeuille({}, <textarea aria-label="Notes" />)
      tirer(screen.getByLabelText('Notes'), 300)
      tirer(dialogue.querySelector('.feuille-titre'), 0, { x: 50 })
      toucher(dialogue.querySelector('.poignee'), 'touchStart', 300, 100)
      act(() => { vi.advanceTimersByTime(16) })
      toucher(dialogue.querySelector('.poignee'), 'touchMove', 310, 200)
      toucher(dialogue.querySelector('.poignee'), 'touchEnd', 310, 200)
      expect(onFermer).not.toHaveBeenCalled()
    })

    it('au bureau : la saisie EN PLACE (aucune poignée) ne se tire pas', () => {
      vi.useFakeTimers()
      const ancre = document.createElement('div')
      document.body.appendChild(ancre)
      const enPlace = monterFeuille({ variante: 'popover', ancre })
      expect(enPlace.dialogue.querySelector('.poignee')).toBeNull()
      tirer(enPlace.dialogue.querySelector('.feuille-titre'), 300)
      expect(enPlace.onFermer).not.toHaveBeenCalled()
      ancre.remove()
    })
  })

  it('Raccord F2 — `historique={false}` (la fiche, déjà dans l\'adresse) ne pose aucune entrée', async () => {
    const pose = vi.spyOn(window.history, 'pushState')
    render(<FeuilleACrans ouverte titre="Fiche" historique={false} onFermer={() => {}}><button type="button">x</button></FeuilleACrans>)
    await new Promise((fin) => { setTimeout(fin, 5) })
    expect(pose).not.toHaveBeenCalled()
  })
})

describe('R2-041 — SelecteurQuand : l\'heure et le jour s\'écrivent à la sortie du champ', () => {
  const valeur = { jour_prevu: '2026-11-17', moment: '', heure_debut: null, quelque_jour: false }

  it('taper 1145 pas à pas n\'écrit rien ; la sortie du champ écrit 11:45 une seule fois', () => {
    const onChoisir = vi.fn()
    render(<SelecteurQuand valeur={valeur} aujourdhui="2026-11-17" onChoisir={onChoisir} />)
    const champ = screen.getByLabelText('Heure')
    // le navigateur rend une heure « valide » dès le 3e chiffre (11:04), puis 11:45
    fireEvent.change(champ, { target: { value: '11:04' } })
    fireEvent.change(champ, { target: { value: '11:45' } })
    expect(onChoisir).not.toHaveBeenCalled()
    expect(champ).toHaveValue('11:45')
    fireEvent.blur(champ)
    expect(onChoisir).toHaveBeenCalledTimes(1)
    expect(onChoisir).toHaveBeenCalledWith(expect.objectContaining({ jour_prevu: '2026-11-17', heure_debut: '11:45' }))
    fireEvent.blur(champ) // rien de neuf : pas de seconde écriture
    expect(onChoisir).toHaveBeenCalledTimes(1)
  })

  it('Entrée valide l\'heure ; le jour choisi s\'écrit aussi à la sortie, jamais une année partielle', () => {
    const onChoisir = vi.fn()
    render(<SelecteurQuand valeur={{ ...valeur, jour_prevu: '2026-11-20' }} aujourdhui="2026-11-17" onChoisir={onChoisir} />)
    const heure = screen.getByLabelText('Heure')
    fireEvent.change(heure, { target: { value: '09:30' } })
    fireEvent.keyDown(heure, { key: 'Enter' })
    expect(onChoisir).toHaveBeenLastCalledWith(expect.objectContaining({ heure_debut: '09:30' }))
    onChoisir.mockClear()
    const jour = screen.getByLabelText('Choisir un jour')
    fireEvent.change(jour, { target: { value: '0002-11-27' } })
    fireEvent.change(jour, { target: { value: '2026-11-27' } })
    expect(onChoisir).not.toHaveBeenCalled()
    fireEvent.blur(jour)
    expect(onChoisir).toHaveBeenCalledTimes(1)
    expect(onChoisir).toHaveBeenCalledWith(expect.objectContaining({ jour_prevu: '2026-11-27' }))
  })

  it('R3-067 (choix C-22) — « Reporter à {jour} » qui tombe demain n\'a plus sa tuile : une seule « Demain » ; « Choisir un jour » devient « Calendrier… »', () => {
    const tuiles = () => screen.getAllByRole('radio').map((r) => r.querySelector('b').textContent)
    const onChoisir = vi.fn()
    const { unmount } = render(<SelecteurQuand valeur={valeur} aujourdhui="2026-11-17" reporterA="2026-11-18" onChoisir={onChoisir} />)
    expect(tuiles()).toEqual(["Aujourd'hui", 'Demain', 'Ce soir', 'Calendrier…', 'Plus tard', 'Sans jour'])
    fireEvent.click(screen.getByRole('radio', { name: /^Demain/ }))
    expect(onChoisir).toHaveBeenCalledWith(expect.objectContaining({ jour_prevu: '2026-11-18' }))
    unmount()
    // vendredi → le prochain jour travaillé est lundi : les deux tuiles disent deux jours différents, elles restent
    render(<SelecteurQuand valeur={{ ...valeur, jour_prevu: '2026-11-20' }} aujourdhui="2026-11-20" reporterA="2026-11-23" onChoisir={onChoisir} />)
    expect(tuiles()).toEqual(["Aujourd'hui", 'Demain', 'Ce soir', 'Reporter à lun. 23', 'Calendrier…', 'Plus tard', 'Sans jour'])
  })

  it('R3-060 — démonté avec une heure ou un jour tapés et pas encore écrits (retour arrière, fiche changée) : ils partent, une seule fois', () => {
    const onChoisir = vi.fn()
    const { unmount } = render(<SelecteurQuand valeur={valeur} aujourdhui="2026-11-17" onChoisir={onChoisir} />)
    fireEvent.change(screen.getByLabelText('Heure'), { target: { value: '16:30' } })
    unmount()
    expect(onChoisir).toHaveBeenCalledTimes(1)
    expect(onChoisir).toHaveBeenCalledWith(expect.objectContaining({ jour_prevu: '2026-11-17', heure_debut: '16:30' }))
    // déjà écrite à la sortie du champ : le démontage n'écrit rien de plus
    onChoisir.mockClear()
    const second = render(<SelecteurQuand valeur={valeur} aujourdhui="2026-11-17" onChoisir={onChoisir} />)
    const champ = screen.getByLabelText('Heure')
    fireEvent.change(champ, { target: { value: '09:15' } })
    fireEvent.blur(champ)
    second.unmount()
    expect(onChoisir).toHaveBeenCalledTimes(1)
    // un jour entier tapé part avec l'heure tapée, en une écriture
    onChoisir.mockClear()
    const troisieme = render(<SelecteurQuand valeur={{ ...valeur, jour_prevu: '2026-11-20' }} aujourdhui="2026-11-17" onChoisir={onChoisir} />)
    fireEvent.click(screen.getByRole('radio', { name: /Choisir un jour|Calendrier/ }))
    fireEvent.change(screen.getByLabelText('Choisir un jour'), { target: { value: '2026-11-27' } })
    fireEvent.change(screen.getByLabelText('Heure'), { target: { value: '08:00' } })
    troisieme.unmount()
    expect(onChoisir).toHaveBeenCalledTimes(1)
    expect(onChoisir).toHaveBeenCalledWith(expect.objectContaining({ jour_prevu: '2026-11-27', heure_debut: '08:00' }))
  })
})

describe('R3-062 — fiche ouverte (panneau du bureau) : `j` / `k` font suivre la fiche, comme Linear', () => {
  function Liste() {
    const ouvrirFiche = useOuvrirFiche()
    const [params] = useSearchParams()
    const lieu = useLocation()
    const type = useNavigationType()
    const racine = useClavierListe(() => {})
    const ouverte = params.get('tache')
    return (
      <div className="tch">
        <div ref={racine}>
          {[['tache', 1], ['activite', 7], ['tache', 2]].map(([genre, id]) => (
            <div key={`${genre}:${id}`} data-ligne={`${genre}:${id}`}>
              <button type="button" className="ligne-corps-bouton" onClick={() => { if (genre === 'tache') ouvrirFiche(id) }}>{`ligne ${genre} ${id}`}</button>
            </div>
          ))}
        </div>
        {ouverte ? <div data-fiche={ouverte}>{`fiche ${ouverte}`}</div> : null}
        <output data-testid="lieu">{`${lieu.search} ${type}`}</output>
      </div>
    )
  }

  it('j sur la ligne suivante change la fiche ouverte (entrée d\'historique REMPLACÉE) ; une activité ne la change pas', () => {
    render(<MemoryRouter initialEntries={['/taches/aujourdhui']}><Liste /></MemoryRouter>)
    // sans fiche ouverte, j ne fait que parcourir (comme avant)
    fireEvent.keyDown(document.body, { key: 'j' })
    expect(screen.getByText('ligne tache 1')).toHaveFocus()
    expect(screen.queryByText(/^fiche/)).toBeNull()
    fireEvent.click(screen.getByText('ligne tache 1'))
    expect(screen.getByText('fiche 1')).toBeInTheDocument()
    fireEvent.keyDown(screen.getByText('ligne tache 1'), { key: 'j' })
    expect(screen.getByText('ligne activite 7')).toHaveFocus()
    expect(screen.getByText('fiche 1')).toBeInTheDocument() // une activité n'a pas de fiche de tâche
    fireEvent.keyDown(screen.getByText('ligne activite 7'), { key: 'j' })
    expect(screen.getByText('ligne tache 2')).toHaveFocus()
    expect(screen.getByText('fiche 2')).toBeInTheDocument()
    expect(screen.getByTestId('lieu')).toHaveTextContent('?tache=2 REPLACE')
    fireEvent.keyDown(screen.getByText('ligne tache 2'), { key: 'k' })
    fireEvent.keyDown(screen.getByText('ligne activite 7'), { key: 'k' })
    expect(screen.getByText('fiche 1')).toBeInTheDocument()
  })
})

describe('R3-060 — « En attente de… » : un nom tapé n\'est jamais perdu à la fermeture', () => {
  const item = { id: 20, type: 'tache', titre: 'Devis Settat', en_attente_de: '' }

  it('fermée sans « En attente » (Échap, croix, retour) : le nom tapé est enregistré, une seule fois', () => {
    const onValider = vi.fn()
    const { unmount } = render(<FeuilleAttente item={item} onValider={onValider} />)
    fireEvent.change(screen.getByLabelText('De qui ou de quoi ?'), { target: { value: 'Karim ' } })
    unmount()
    expect(onValider).toHaveBeenCalledTimes(1)
    expect(onValider).toHaveBeenCalledWith('Karim')
  })

  it('validée par « En attente » : rien de plus à la fermeture ; rien tapé, rien d\'écrit', () => {
    const onValider = vi.fn()
    const premiere = render(<FeuilleAttente item={item} onValider={onValider} />)
    fireEvent.change(screen.getByLabelText('De qui ou de quoi ?'), { target: { value: 'Karim' } })
    fireEvent.click(screen.getByRole('button', { name: 'En attente' }))
    premiere.unmount()
    expect(onValider).toHaveBeenCalledTimes(1)
    onValider.mockClear()
    render(<FeuilleAttente item={{ ...item, en_attente_de: 'Nadia' }} onValider={onValider} />).unmount()
    expect(onValider).not.toHaveBeenCalled()
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
