import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../lib/gestes'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../../api/axios')).default
const { default: Aujourdhui } = await import('../../../pages/taches/Aujourdhui')

/* TCH79 — menu ⋯ d'Aujourd'hui (Alléger, Réorganiser, Sélectionner, En faire mon accueil) et feuille
   « Alléger ma journée » : rien coché d'avance, « 3 retournées aux projets » annoncé. Sur aujourdhui.json
   et journee_ecrite.json. */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))
const unJour = () => {
  const d = contrat('aujourdhui')
  d.carte_du_moment = null
  d.propose.pour_objectif = []
  return d
}

function servir(donnees) {
  api.get.mockResolvedValue({ data: donnees })
  api.post.mockImplementation((url) => {
    if (url === '/taches/journee/alleger/') return Promise.resolve({ data: { ...contrat('journee_ecrite'), renvoyees: [41, 42, 43] } })
    if (url === '/taches/taches/lot/') return Promise.resolve({ data: { appliquees: [20, 42], refusees: [], geste_id: 78 } })
    return Promise.resolve({ data: {} })
  })
  api.post.mockClear()
}

async function ouvrirMenu(nom) {
  await userEvent.click(screen.getByRole('button', { name: "Plus d'actions" }))
  await userEvent.click(await screen.findByRole('menuitem', { name: nom }))
}

const monter = () => render(<MemoryRouter><Aujourdhui /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
  window.localStorage.clear()
  Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true })
})

describe('TCH79 — menu ⋯ d\'Aujourd\'hui', () => {
  it('propose les quatre actions de l\'écran puis celles de la coquille', async () => {
    servir(unJour())
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: "Plus d'actions" }))
    const noms = (await screen.findAllByRole('menuitem')).map((n) => n.textContent)
    expect(noms).toEqual([
      'Alléger ma journée', 'Réorganiser', 'Sélectionner', 'En faire mon accueil',
      'Revue de la semaine', 'Mon rythme', 'Supprimées récemment', 'Réglages',
    ])
  })

  it('« En faire mon accueil » poste la route d\'Aujourd\'hui sur auth/mobile-home-route/', async () => {
    servir(unJour())
    monter()
    await screen.findByText('Devis Settat')
    await ouvrirMenu('En faire mon accueil')
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/auth/mobile-home-route/', { route: '/taches/aujourdhui' }))
  })

  it('hors ligne, Alléger et l\'accueil sont grisés : rien n\'est posté', async () => {
    servir(unJour())
    monter()
    await screen.findByText('Devis Settat')
    api.post.mockClear()
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
    act(() => { window.dispatchEvent(new Event('offline')) })
    await ouvrirMenu('Alléger ma journée')
    expect(screen.queryByRole('dialog', { name: 'Alléger ma journée' })).toBeNull()
    await ouvrirMenu('En faire mon accueil')
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.getAllByRole('status').some((n) => n.textContent.includes('Possible une fois connecté'))).toBe(true)
  })
})

describe('TCH79 — feuille « Alléger ma journée »', () => {
  it('rien n\'est coché d\'avance ; on coche ce qu\'on garde ; « 3 retournées aux projets » est annoncé', async () => {
    servir(unJour())
    monter()
    await screen.findByText('Devis Settat')
    await ouvrirMenu('Alléger ma journée')
    const feuille = await screen.findByRole('dialog', { name: 'Alléger ma journée' })
    // R2-026 — l'aide tient en une ligne ; rien coché : « Tout renvoyer aux projets », jamais un « Garder ces 0 » mort
    expect(feuille).toHaveTextContent('Coche ce que tu gardes ; le reste retourne à ses projets, sans report.')
    const cases = within(feuille).getAllByRole('checkbox')
    expect(cases.map((c) => c.getAttribute('aria-checked'))).toEqual(cases.map(() => 'false'))
    expect(within(feuille).getByRole('button', { name: 'Tout renvoyer aux projets' })).not.toHaveAttribute('aria-disabled')
    expect(within(feuille).queryByRole('button', { name: 'Garder ces 0' })).toBeNull()
    await userEvent.click(within(feuille).getByRole('checkbox', { name: /Timbres/ }))
    await userEvent.click(within(feuille).getByRole('button', { name: 'Garder celle-ci' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/journee/alleger/', { jour: '2026-11-17', garder: [42] }, expect.anything(),
    ))
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('3 retournées aux projets')
    expect(screen.queryByRole('dialog', { name: 'Alléger ma journée' })).toBeNull()
  })

  it('les activités ERP et les tâches à échéance aujourd\'hui ne sont pas proposées (elles restent)', async () => {
    const d = unJour()
    d.journee[0].echeance = '2026-11-17'
    servir(d)
    monter()
    await screen.findByText('Devis Settat')
    await ouvrirMenu('Alléger ma journée')
    const feuille = await screen.findByRole('dialog', { name: 'Alléger ma journée' })
    expect(within(feuille).queryByText('Timbres')).toBeNull()
    expect(within(feuille).queryByText('Rappeler Benali')).toBeNull()
    expect(within(feuille).getByText('Devis Settat')).toBeInTheDocument()
  })

  it('hors ligne : Garder est grisé', async () => {
    servir(unJour())
    monter()
    await screen.findByText('Devis Settat')
    await ouvrirMenu('Alléger ma journée')
    await screen.findByRole('dialog', { name: 'Alléger ma journée' })
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
    act(() => { window.dispatchEvent(new Event('offline')) })
    const feuille = screen.getByRole('dialog', { name: 'Alléger ma journée' })
    expect(within(feuille).getByRole('checkbox', { name: /Timbres/ })).toBeDisabled()
    await userEvent.click(within(feuille).getByRole('button', { name: 'Tout renvoyer aux projets' }))
    expect(api.post).not.toHaveBeenCalledWith('/taches/journee/alleger/', expect.anything(), expect.anything())
  })

  it('R2-026 — rien coché : « Tout renvoyer aux projets » renvoie tout (garder vide)', async () => {
    servir(unJour())
    monter()
    await screen.findByText('Devis Settat')
    await ouvrirMenu('Alléger ma journée')
    const feuille = await screen.findByRole('dialog', { name: 'Alléger ma journée' })
    await userEvent.click(within(feuille).getByRole('button', { name: 'Tout renvoyer aux projets' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/journee/alleger/', { jour: '2026-11-17', garder: [] }, expect.anything(),
    ))
  })

  it('R2-026 — rien à alléger (bilan fait, ou aucune tâche que la feuille peut renvoyer) : l’entrée n’est pas offerte', async () => {
    const bilanFait = unJour()
    bilanFait.plan = { ...bilanFait.plan, cloture_le: '2026-11-17T19:00:00+01:00' }
    servir(bilanFait)
    const { unmount } = monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: "Plus d'actions" }))
    expect((await screen.findAllByRole('menuitem')).map((n) => n.textContent)).not.toContain('Alléger ma journée')
    unmount()
    const rien = unJour()
    for (const cle of ['essentiel', 'journee', 'ce_soir']) rien[cle] = rien[cle].filter((it) => it.type !== 'tache')
    servir(rien)
    monter()
    await screen.findByText('Rappeler Benali')
    await userEvent.click(screen.getByRole('button', { name: "Plus d'actions" }))
    expect((await screen.findAllByRole('menuitem')).map((n) => n.textContent)).not.toContain('Alléger ma journée')
  })
})

describe('TCH79 — Réorganiser et Sélectionner', () => {
  const deuxTaches = () => {
    const d = unJour()
    d.journee = [d.journee[0], { ...d.journee[0], id: 43, titre: 'Appeler Lydec' }]
    return d
  }

  it('Réorganiser : ▼ descend la tâche AU TOUCHER et poste reordonner/ avec ses voisines', async () => {
    servir(deuxTaches())
    monter()
    await screen.findByText('Timbres')
    await ouvrirMenu('Réorganiser')
    await userEvent.click(screen.getByRole('button', { name: 'Descendre « Timbres »' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/42/reordonner/', { liste: 'jour', avant_id: 43, apres_id: null }))
    const titres = [...document.querySelectorAll('[data-ligne^="tache:4"] .titre')].map((n) => n.textContent)
    expect(titres).toEqual(['Appeler Lydec', 'Timbres'])
    expect(screen.getAllByRole('status').some((n) => n.textContent.includes('Timbres : position 2 sur 2'))).toBe(true)
  })

  it('Réorganiser : un refus du serveur remet la ligne et le dit', async () => {
    servir(deuxTaches())
    api.post.mockRejectedValue(Object.assign(new Error('x'), { response: { status: 400, data: { detail: 'Refusé.' }, headers: {} } }))
    monter()
    await screen.findByText('Timbres')
    await ouvrirMenu('Réorganiser')
    await userEvent.click(screen.getByRole('button', { name: 'Descendre « Timbres »' }))
    await waitFor(() => {
      const titres = [...document.querySelectorAll('[data-ligne^="tache:4"] .titre')].map((n) => n.textContent)
      expect(titres).toEqual(['Timbres', 'Appeler Lydec'])
    })
  })

  it('Sélectionner : on coche deux tâches, « 2 sélectionnées », Terminer poste lot/', async () => {
    servir(deuxTaches())
    monter()
    await screen.findByText('Timbres')
    await ouvrirMenu('Sélectionner')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sélectionner : Timbres' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sélectionner : Appeler Lydec' }))
    const barre = screen.getByRole('toolbar', { name: 'Actions sur la sélection' })
    expect(barre).toHaveTextContent('2 sélectionnées')
    await userEvent.click(within(barre).getByRole('button', { name: 'Terminer' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/taches/lot/', { ids: [42, 43], action: 'terminer' }, expect.anything(),
    ))
    await waitFor(() => expect(screen.queryByRole('toolbar')).toBeNull())
  })
})
