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

/* TCH78 — « Proposé pour aujourd'hui » sur aujourdhui.json (3 lignes pour l'objectif) et
   journee_ecrite.json : la raison de chaque ligne est affichée ; « Garder ces N » poste le mode
   express puis met le focus sur Prévu avec l'invite ★ ; jamais d'étoile sur Proposé. */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))
const journee = () => {
  const d = contrat('aujourdhui')
  d.carte_du_moment = null // pas de carte « Garder » : le bouton du bloc Proposé est celui qu'on teste
  d.propose.suite_par_projet = null
  return d
}

function servir(donnees) {
  api.get.mockImplementation((url, options) => {
    if (url !== '/taches/aujourdhui/') return Promise.reject(new Error(`GET inattendu ${url}`))
    return Promise.resolve({ data: options?.params?.tout ? { ...donnees, propose: { ...donnees.propose, suite_par_projet: contrat('aujourdhui').propose.suite_par_projet } } : donnees })
  })
  api.post.mockImplementation((url) => {
    if (url === '/taches/journee/planifier/') return Promise.resolve({ data: contrat('journee_ecrite') })
    return Promise.resolve({ data: {} })
  })
}

const monter = () => render(<MemoryRouter><Aujourdhui /></MemoryRouter>)
const proposé = () => screen.getByRole('region', { name: "Proposé pour aujourd'hui" })

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
  window.localStorage.clear()
  Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true })
})

describe('TCH78 — Proposé pour aujourd\'hui', () => {
  it('chaque ligne dit sa raison ; l\'en-tête dit « En tête : … » ; jamais d\'étoile', async () => {
    servir(journee())
    monter()
    await screen.findByText('Déclaration TVA')
    const bloc = proposé()
    expect(within(bloc).getByText('En tête : échéance jeudi.')).toBeInTheDocument()
    const lignes = [...bloc.querySelectorAll('[data-ligne]')]
    expect(lignes.map((l) => l.querySelector('.titre').textContent)).toEqual(['Déclaration TVA', 'Ranger le bureau', 'Préparer formation'])
    expect(lignes.map((l) => l.querySelector('.explique').textContent)).toEqual(['échéance jeudi', 'prévue hier', 'prochaine action de Équipe'])
    expect(within(bloc).queryByRole('checkbox', { name: /Essentielle/ })).toBeNull()
  })

  it('la prochaine action d\'un projet de priorité haute : « En tête : priorité haute. »', async () => {
    const d = journee()
    d.propose.pour_objectif = [d.propose.pour_objectif[2]]
    servir(d)
    monter()
    await screen.findByText('Préparer formation')
    expect(within(proposé()).getByText('En tête : priorité haute.')).toBeInTheDocument()
  })

  it('« Garder » sur une ligne la garde seule, mode express', async () => {
    servir(journee())
    monter()
    await screen.findByText('Déclaration TVA')
    const ligne = proposé().querySelector('[data-ligne="tache:41"]')
    await userEvent.click(within(ligne).getByRole('button', { name: 'Garder' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/journee/planifier/',
      { jour: '2026-11-17', mode: 'express', lignes: [{ type: 'tache', id: 41 }], essentielles: [], triage: [] },
      expect.anything(),
    ))
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('1 gardée')
  })

  it('« Garder ces 3 » garde tout, annonce « 3 gardées », invite « Touche ★ » et met le focus sur Prévu', async () => {
    servir(journee())
    monter()
    await screen.findByText('Déclaration TVA')
    await userEvent.click(within(proposé()).getByRole('button', { name: 'Garder ces 3' }))
    await waitFor(() => {
      const corps = api.post.mock.calls.find((c) => c[0] === '/taches/journee/planifier/')[1]
      expect(corps.lignes).toEqual([{ type: 'tache', id: 21 }, { type: 'tache', id: 41 }, { type: 'tache', id: 30 }])
    })
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('3 gardées')
    const prevu = screen.getByText('Touche ★ pour ton essentiel').closest('section')
    expect(prevu.querySelector('.section-titre')).toHaveTextContent('Prévu')
    await waitFor(() => expect(document.activeElement).toBe(prevu))
  })

  it('en surcharge : « 5 h 10 pour 4 h de libre » à côté de Garder', async () => {
    const d = journee()
    Object.assign(d.propose.charge, { minutes_estimees: 310, disponible_minutes: 240, surcharge: true })
    servir(d)
    monter()
    expect(await screen.findByText('5 h 10 pour 4 h de libre')).toBeInTheDocument()
  })

  it('« Voir toutes les tâches de mes projets (6) » relit avec tout=1, déplie par projet, puis Masquer', async () => {
    servir(journee())
    monter()
    await screen.findByText('Déclaration TVA')
    await userEvent.click(screen.getByRole('button', { name: 'Voir toutes les tâches de mes projets (6)' }))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/taches/aujourdhui/', { params: { tout: 1 } }))
    const groupe = await screen.findByRole('group', { name: 'Équipe' })
    expect(within(groupe).getByText('Réserver la salle')).toBeInTheDocument()
    expect(within(groupe).getByText('puis dans Équipe')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Masquer' }))
    expect(screen.queryByRole('group', { name: 'Équipe' })).toBeNull()
  })

  it('une tâche du tour des projets déjà prévue plus tard dit « prévue {jour} »', async () => {
    servir(journee())
    api.get.mockImplementation((url, options) => {
      const d = journee()
      if (options?.params?.tout) {
        d.propose.suite_par_projet = contrat('aujourdhui').propose.suite_par_projet
        d.propose.suite_par_projet[0].items[0].jour_prevu = '2026-11-23'
      }
      return Promise.resolve({ data: d })
    })
    monter()
    await userEvent.click(await screen.findByRole('button', { name: /Voir toutes les tâches de mes projets/ }))
    expect(await screen.findByText('prévue lun. 23')).toBeInTheDocument()
  })

  it('objectif couvert : « Objectif couvert par ce que tu as gardé. » et le lien reste', async () => {
    const d = journee()
    d.propose.pour_objectif = []
    servir(d)
    monter()
    expect(await screen.findByText('Objectif couvert par ce que tu as gardé.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Voir toutes les tâches de mes projets (6)' })).toBeInTheDocument()
  })

  it('après Alléger : en-tête replié « Proposé pour aujourd\'hui · revient demain », aucune ligne', async () => {
    const d = journee()
    Object.assign(d.propose, { replie: true, pour_objectif: [], reste_nb: 6 })
    servir(d)
    monter()
    const entete = await screen.findByRole('button', { name: /Proposé pour aujourd'hui/ })
    expect(entete).toHaveTextContent('· revient demain')
    expect(entete).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Déclaration TVA')).toBeNull()
  })

  it('hors ligne : Garder ces 3 est grisé et ne poste rien', async () => {
    servir(journee())
    monter()
    await screen.findByText('Déclaration TVA')
    api.post.mockClear()
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
    act(() => { window.dispatchEvent(new Event('offline')) })
    const bouton = within(proposé()).getByRole('button', { name: 'Garder ces 3' })
    expect(bouton).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(bouton)
    expect(api.post).not.toHaveBeenCalled()
  })
})
