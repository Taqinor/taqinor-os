import { createElement as h } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import CoquilleTaches from '../coquille/CoquilleTaches'
import BandeauConflit from '../ui/BandeauConflit'
import LigneTache from '../ui/LigneTache'
import { actionDeTouche, SEQUENCE_MS, useClavierListe } from './clavierListe'
import {
  annoncer, configurerGestes, DUREE_TOAST_MS, fermerToast, proposerAnnuler, reinitialiserGestes, useGeste,
} from './gestes'

/* TCH46 — critères (1)-(4) de « Accessibilité » (spec-7 §6) :
   (1) lecteur d'écran, je coche → `role=status` dit « Fait : <titre> » ;
   (2) toast focalisé, 8 s passent → il reste ;
   (3) « Messages sans délai » allumé → il reste jusqu'à fermeture ;
   (4) toute action de ligne au clavier par Tab → Actions → item.
   + le bandeau de conflit et le clavier des listes (j/k/Espace/e/d/m/x/h/*, muet sous dialogue). */

const toastTexte = () => document.querySelector('.toast > span')?.textContent ?? null
const item = () => structuredClone(exempleContrat('taches', 'item'))

function Page({ onTerminer = vi.fn().mockResolvedValue({}) }) {
  const { annoncer: dire } = useGeste()
  return h('div', { role: 'list' },
    h(LigneTache, { item: item(), aujourdhui: '2026-11-17', onTerminer, onAnnonce: dire, reporterLibelle: 'lun. 23' }))
}

const monter = (enfant) => render(
  h(MemoryRouter, { initialEntries: ['/taches/aujourdhui'] },
    h(CoquilleTaches, { ecran: 'aujourdhui', titre: "Aujourd'hui" }, enfant)),
)

// la coquille garde « Messages sans délai » sur l'appareil (R2-088) : un test ne la reçoit jamais d'un autre
beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); reinitialiserGestes(); window.localStorage.clear() })
afterEach(() => { reinitialiserGestes(); vi.useRealTimers() })

describe('TCH46 — (1) annonces lues par role=status', () => {
  it('cocher dit « Fait : titre » dans la région status', async () => {
    monter(h(Page))
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(screen.getByRole('checkbox', { name: /Marquer/ }))
    expect(await screen.findByRole('status')).toHaveTextContent('Fait : Devis Settat')
  })

  it('la même phrase annoncée deux fois est relue (le texte change de forme)', () => {
    monter(h('p', null, 'x'))
    act(() => annoncer('Annulé'))
    const premier = screen.getByRole('status').textContent
    act(() => annoncer('Annulé'))
    expect(screen.getByRole('status').textContent).not.toBe(premier)
    expect(screen.getByRole('status')).toHaveTextContent('Annulé')
  })

  it('un geste avec « Annuler » annonce son message ; annuler dit « Annulé »', async () => {
    const onAnnuler = vi.fn().mockResolvedValue({})
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', annonce: 'Fait : Appeler Karim', onAnnuler }) })
    expect(screen.getByRole('status')).toHaveTextContent('Fait : Appeler Karim')
    expect(toastTexte()).toBe('Faite')
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onAnnuler).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).toHaveTextContent('Annulé')
    expect(screen.queryByRole('button', { name: 'Annuler' })).toBeNull()
  })

  it('vague 2 — un bouton qui n\'est pas « Annuler » (« Reprendre ») ne fait jamais annoncer « Annulé »', async () => {
    const onAnnuler = vi.fn()
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Pas ajoutée : réseau', libelle: 'Reprendre', onAnnuler }) })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(screen.getByRole('button', { name: 'Reprendre' }))
    expect(onAnnuler).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).not.toHaveTextContent('Annulé')
    // …et un geste qui le précise annonce SA phrase
    act(() => { proposerAnnuler({ message: 'Pas ajoutée', libelle: 'Reprendre', apres: 'Phrase reprise', onAnnuler }) })
    await user.click(screen.getByRole('button', { name: 'Reprendre' }))
    expect(screen.getByRole('status')).toHaveTextContent('Phrase reprise')
  })

  it('une annulation refusée par le serveur est DITE en français, jamais avalée', async () => {
    const onAnnuler = vi.fn().mockRejectedValue({ response: { status: 400, data: { detail: 'Tâche verrouillée.' }, headers: {} } })
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler }) })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(toastTexte()).toBe('Tâche verrouillée.')
  })
})

describe('TCH46 — (2) le toast dure 8 s, en pause au survol ou au focus', () => {
  it('sans interaction, il part au bout de 8 s', () => {
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler: vi.fn() }) })
    act(() => { vi.advanceTimersByTime(DUREE_TOAST_MS - 100) })
    expect(toastTexte()).toBe('Faite')
    act(() => { vi.advanceTimersByTime(200) })
    expect(toastTexte()).toBeNull()
  })

  it('focalisé : 8 s passent, il reste ; au blur, il reprend et part', () => {
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler: vi.fn() }) })
    const annuler = screen.getByRole('button', { name: 'Annuler' })
    act(() => { annuler.focus() })
    act(() => { vi.advanceTimersByTime(DUREE_TOAST_MS + 1000) })
    expect(toastTexte()).toBe('Faite')
    act(() => { annuler.blur() })
    act(() => { vi.advanceTimersByTime(DUREE_TOAST_MS + 100) })
    expect(toastTexte()).toBeNull()
  })

  it('survolé : en pause ; le temps déjà écoulé est compté à la reprise', () => {
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler: vi.fn() }) })
    const toast = screen.getByRole('group', { name: 'Geste effectué' })
    act(() => { vi.advanceTimersByTime(6000) })
    fireEvent.mouseEnter(toast)
    act(() => { vi.advanceTimersByTime(20000) })
    expect(toastTexte()).toBe('Faite')
    fireEvent.mouseLeave(toast)
    act(() => { vi.advanceTimersByTime(1500) })
    expect(toastTexte()).toBe('Faite')
    act(() => { vi.advanceTimersByTime(700) })
    expect(toastTexte()).toBeNull()
  })

  it('un seul toast à la fois : le nouveau remplace l\'ancien', () => {
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler: vi.fn() }) })
    act(() => { proposerAnnuler({ message: 'Reportée à lun. 23', onAnnuler: vi.fn() }) })
    expect(toastTexte()).toBe('Reportée à lun. 23')
    expect(document.querySelectorAll('.toast')).toHaveLength(1)
    expect(screen.getAllByRole('group', { name: 'Geste effectué' })).toHaveLength(1)
  })

  it('un message sans geste à défaire n\'a pas de bouton Annuler', () => {
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: "Close dans l'ERP" }) })
    expect(toastTexte()).toBe("Close dans l'ERP")
    expect(screen.queryByRole('button', { name: 'Annuler' })).toBeNull()
  })
})

describe('TCH46 — (3) « Messages sans délai »', () => {
  it('allumé : le toast reste jusqu\'à ce qu\'on le ferme', async () => {
    configurerGestes({ sansDelai: true })
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler: vi.fn() }) })
    act(() => { vi.advanceTimersByTime(10 * DUREE_TOAST_MS) })
    expect(toastTexte()).toBe('Faite')
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(screen.getByRole('button', { name: 'Fermer' }))
    expect(toastTexte()).toBeNull()
  })

  it('éteint de nouveau : un toast en cours reprend ses 8 s', () => {
    configurerGestes({ sansDelai: true })
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler: vi.fn() }) })
    act(() => { configurerGestes({ sansDelai: false }) })
    act(() => { vi.advanceTimersByTime(DUREE_TOAST_MS + 100) })
    expect(toastTexte()).toBeNull()
  })

  it('fermerToast ferme à la main', () => {
    monter(h('p', null, 'x'))
    act(() => { proposerAnnuler({ message: 'Faite', onAnnuler: vi.fn() }) })
    act(() => fermerToast())
    expect(toastTexte()).toBeNull()
  })
})

describe('TCH46 — (4) toute action de ligne au clavier : Tab → Actions → item', () => {
  it('le bouton Actions est atteint par Tab dans la coquille et ouvre le menu', async () => {
    monter(h(Page))
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const actions = screen.getByRole('button', { name: 'Actions pour « Devis Settat »' })
    for (let i = 0; i < 20 && document.activeElement !== actions; i += 1) await user.tab()
    expect(actions).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('menuitem', { name: 'Reporter à lun. 23' })).toBeInTheDocument()
  })
})

describe('TCH46 — bandeau de conflit', () => {
  it('nomme l\'autre appareil, offre les deux choix et l\'annonce une fois', async () => {
    const onGarder = vi.fn()
    const onPrendre = vi.fn()
    monter(h('p', null, 'x'))
    render(h(BandeauConflit, { heure: '10:42', onGarder, onPrendre }))
    expect(screen.getByText('Modifiée sur ton autre appareil à 10:42')).toBeInTheDocument()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(screen.getByRole('button', { name: 'Garder la mienne' }))
    await user.click(screen.getByRole('button', { name: "Prendre l'autre" }))
    expect(onGarder).toHaveBeenCalledTimes(1)
    expect(onPrendre).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).toHaveTextContent("Modifiée sur ton autre appareil : choisis Garder la mienne ou Prendre l'autre")
  })

  it('la coquille le monte sous l\'en-tête avec sa prop `conflit`', () => {
    render(h(MemoryRouter, { initialEntries: ['/taches/aujourdhui'] },
      h(CoquilleTaches, { ecran: 'aujourdhui', titre: "Aujourd'hui", conflit: { heure: '10:42', onGarder: () => {}, onPrendre: () => {} } })))
    expect(screen.getByRole('group', { name: 'Conflit entre appareils' })).toBeInTheDocument()
  })
})

describe('TCH46 — clavier des listes', () => {
  function Liste({ surAction }) {
    const racine = useClavierListe(surAction)
    return h('div', { ref: racine },
      ['a', 'b', 'c'].map((c) => h('div', { key: c, 'data-ligne': `tache:${c}` },
        h('button', { type: 'button', className: 'ligne-corps-bouton' }, `ligne ${c}`))),
      h('input', { 'aria-label': 'champ' }))
  }
  const touche = (key, extra = {}) => fireEvent.keyDown(document.activeElement ?? document.body, { key, ...extra })

  it('j et k parcourent les lignes, la première au premier j', () => {
    render(h(Liste, { surAction: vi.fn() }))
    touche('j')
    expect(screen.getByText('ligne a')).toHaveFocus()
    touche('j')
    expect(screen.getByText('ligne b')).toHaveFocus()
    touche('j')
    touche('j')
    expect(screen.getByText('ligne c')).toHaveFocus()
    touche('k')
    expect(screen.getByText('ligne b')).toHaveFocus()
  })

  it.each([
    [' ', 'terminer'], ['e', 'renommer'], ['d', 'quand'], ['m', 'deplacer'], ['x', 'selectionner'],
    ['h', 'heure'], ['*', 'essentiel'],
  ])('« %s » sur une ligne = %s', (key, action) => {
    const surAction = vi.fn()
    render(h(Liste, { surAction }))
    screen.getByText('ligne b').focus()
    touche(key)
    expect(surAction).toHaveBeenCalledWith(action, expect.objectContaining({ cle: 'tache:b' }))
  })

  it('Alt+↑/↓ réordonnent, Maj+↓ allonge, Ctrl/⌘ Z annule', () => {
    const surAction = vi.fn()
    render(h(Liste, { surAction }))
    screen.getByText('ligne a').focus()
    touche('ArrowDown', { altKey: true })
    touche('ArrowUp', { altKey: true })
    touche('ArrowDown', { shiftKey: true })
    touche('z', { ctrlKey: true })
    touche('z', { metaKey: true })
    expect(surAction.mock.calls.map(([a]) => a)).toEqual(['descendre', 'monter', 'allonger', 'annuler', 'annuler'])
  })

  it('aucune touche seule ne fait disparaître une ligne', () => {
    for (const key of ['Delete', 'Backspace', 'Enter', 'Escape', 'a', 'r', 's', 'u']) {
      expect(actionDeTouche({ key })).toBeNull()
    }
  })

  it('muet dans un champ, sous un dialogue, et pendant la séquence g / c', () => {
    const surAction = vi.fn()
    render(h(Liste, { surAction }))
    screen.getByText('ligne a').focus()
    // dans un champ de saisie
    screen.getByLabelText('champ').focus()
    touche('e')
    expect(surAction).not.toHaveBeenCalled()
    // sous un dialogue modal
    screen.getByText('ligne a').focus()
    const dialogue = document.createElement('div')
    dialogue.setAttribute('role', 'dialog')
    dialogue.setAttribute('aria-modal', 'true')
    document.body.appendChild(dialogue)
    touche('e')
    expect(surAction).not.toHaveBeenCalled()
    dialogue.remove()
    // après `g` : la touche suivante appartient à la séquence « g j »
    touche('g')
    touche('d')
    expect(surAction).not.toHaveBeenCalled()
    vi.advanceTimersByTime(SEQUENCE_MS + 50)
    touche('d')
    expect(surAction).toHaveBeenCalledWith('quand', expect.objectContaining({ cle: 'tache:a' }))
  })
})
