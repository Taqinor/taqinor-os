// ODY11 — Tests de la transition signature app ↔ accueil.
// Le point qui compte : la NAVIGATION ne dépend jamais de l'effet. Trois
// chemins, tous vérifiés — API absente (jsdom, et Safari/Firefox anciens),
// mouvement réduit (OS ou préférence app), API présente.
import { describe, it, expect, vi } from 'vitest'
import {
  mouvementReduit, transitionsDisponibles, runAppTransition, marquerIconeSortante,
  NOM_TRANSITION_ICONE,
} from './appTransition'

const docSansApi = { documentElement: { getAttribute: () => null } }
const winSansPref = { matchMedia: () => ({ matches: false }) }

describe('ODY11 — appTransition', () => {
  it('sans View Transitions API : exécute directement, renvoie null', () => {
    const run = vi.fn()
    const t = runAppTransition(run, { doc: docSansApi, win: winSansPref })
    expect(run).toHaveBeenCalledTimes(1)
    expect(t).toBeNull()
  })

  it('prefers-reduced-motion (OS) : INSTANTANÉ, aucune transition démarrée', () => {
    const startViewTransition = vi.fn()
    const run = vi.fn()
    const doc = { ...docSansApi, startViewTransition }
    const win = { matchMedia: () => ({ matches: true }) }
    expect(runAppTransition(run, { doc, win })).toBeNull()
    expect(run).toHaveBeenCalledTimes(1)
    expect(startViewTransition).not.toHaveBeenCalled()
  })

  it('préférence APP data-reduced-motion="true" : INSTANTANÉ aussi', () => {
    const startViewTransition = vi.fn()
    const run = vi.fn()
    const doc = {
      documentElement: { getAttribute: (n) => (n === 'data-reduced-motion' ? 'true' : null) },
      startViewTransition,
    }
    expect(runAppTransition(run, { doc, win: winSansPref })).toBeNull()
    expect(run).toHaveBeenCalledTimes(1)
    expect(startViewTransition).not.toHaveBeenCalled()
  })

  it('API présente et mouvement autorisé : passe par startViewTransition', () => {
    const run = vi.fn()
    const startViewTransition = vi.fn((cb) => { cb(); return { finished: Promise.resolve() } })
    const doc = { ...docSansApi, startViewTransition }
    const t = runAppTransition(run, { doc, win: winSansPref })
    expect(startViewTransition).toHaveBeenCalledTimes(1)
    expect(run).toHaveBeenCalledTimes(1)
    expect(t.finished).toBeInstanceOf(Promise)
  })

  it('une API qui LÈVE ne bloque jamais la navigation', () => {
    const run = vi.fn()
    const doc = {
      ...docSansApi,
      startViewTransition: () => { throw new Error('boom') },
    }
    expect(runAppTransition(run, { doc, win: winSansPref })).toBeNull()
    expect(run).toHaveBeenCalledTimes(1)
  })

  it('transitionsDisponibles / mouvementReduit : feature-detect défensif', () => {
    expect(transitionsDisponibles({ doc: docSansApi })).toBe(false)
    expect(transitionsDisponibles({ doc: { startViewTransition: () => {} } })).toBe(true)
    // Environnement dégradé (pas de matchMedia) : jamais une exception.
    expect(mouvementReduit({ doc: docSansApi, win: {} })).toBe(false)
  })

  it('marquerIconeSortante nomme la pastille puis sait la dénommer', () => {
    const cellule = document.createElement('div')
    cellule.innerHTML = '<span class="app-icon"></span>'
    const pastille = cellule.querySelector('.app-icon')
    const nettoyer = marquerIconeSortante(cellule)
    expect(pastille.style.viewTransitionName).toBe(NOM_TRANSITION_ICONE)
    nettoyer()
    expect(pastille.style.viewTransitionName).toBe('')
  })

  it('marquerIconeSortante sans pastille : no-op sûr', () => {
    expect(() => marquerIconeSortante(null)()).not.toThrow()
    expect(() => marquerIconeSortante(document.createElement('div'))()).not.toThrow()
  })
})
