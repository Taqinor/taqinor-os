import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../api/axios')).default
const { default: Aujourdhui } = await import('./Aujourdhui')

/* TCH76 — l'écran Aujourd'hui rend `aujourdhui.json` : sections dans l'ordre de regles.md §4.1,
   liste gardée sur un rafraîchissement en échec, actions grisées hors ligne, squelette après 1 s,
   rendez-vous externes en lecture seule, état vide « Colle ou dicte tes listes ». */

const donnees = () => structuredClone(exempleContrat('taches', 'aujourdhui'))
const echecReseau = () => Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })

function servir(reponse) {
  api.get.mockImplementation((url) => {
    if (url === '/taches/aujourdhui/') return typeof reponse === 'function' ? reponse() : Promise.resolve({ data: reponse })
    return Promise.reject(new Error(`appel inattendu : GET ${url}`))
  })
}

function monter(url = '/taches/aujourdhui') {
  return render(<MemoryRouter initialEntries={[url]}><Aujourdhui /></MemoryRouter>)
}

function fixerEnLigne(valeur) {
  Object.defineProperty(window.navigator, 'onLine', { value: valeur, configurable: true })
  act(() => { window.dispatchEvent(new Event(valeur ? 'online' : 'offline')) })
}

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
  fixerEnLigne(true)
})
afterEach(() => { vi.useRealTimers() })

describe('TCH76 — ordre vertical et contenu des sections', () => {
  it('rend Essentiel, Toute la journée, Prévu, Ce soir puis les repliés, dans cet ordre', async () => {
    servir(donnees())
    const { container } = monter()
    await screen.findByText('Devis Settat')
    const reperes = [...container.querySelectorAll('.section-titre, .bande-journee, .replie')]
      .map((n) => n.textContent.replace(/\s+/g, ' ').trim())
    expect(reperes[0]).toBe('Essentiel')
    expect(reperes.slice(1, 3).every((t) => t.endsWith('Toute la journée'))).toBe(true)
    expect(reperes.slice(3)).toEqual([
      'Prévu', 'Ce soir', "Proposé pour aujourd'hui", 'À revoir1', "En attente1· 1 en attente d'une autre tâche", 'Faites1',
    ])
  })

  it('met les lignes à leur place : essentiel, rendez-vous à son heure, activité ERP, relances', async () => {
    servir(donnees())
    const { container } = monter()
    await screen.findByText('Devis Settat')
    const essentiel = container.querySelector('.section.premiere')
    expect(within(essentiel).getByText('Devis Settat')).toBeInTheDocument()
    expect(within(essentiel).getByRole('checkbox', { name: /Essentielle : Devis Settat/ })).toBeChecked()
    const prevu = [...container.querySelectorAll('.section')].find((s) => s.textContent.startsWith('Prévu'))
    const titres = [...prevu.querySelectorAll('.titre')].map((t) => t.textContent)
    expect(titres).toEqual(['11:00–12:00 Réunion banque', 'Timbres', 'Rappeler Benali', 'Suivi des relances : 5'])
    expect(within(prevu).getByText('Activité ERP')).toBeInTheDocument()
    expect(container.querySelector('.bande-journee b')).toHaveTextContent('Visite — Karim Benali')
  })

  it('un rendez-vous d\'un agenda externe est en lecture seule : ni case, ni geste', async () => {
    servir(donnees())
    const { container } = monter()
    await screen.findByText('Devis Settat')
    const rdv = container.querySelector('[data-ligne="rdv:2-9f2c1a7b"]')
    expect(rdv).toHaveTextContent('Microsoft 365')
    expect(within(rdv).queryByRole('checkbox')).toBeNull()
    expect(within(rdv).queryByRole('button')).toBeNull()
  })

  it('le sous-titre est le jour long, « Jour non travaillé » un jour chômé', async () => {
    servir({ ...donnees(), jour_ouvre: false })
    monter()
    expect(await screen.findByText('Jour non travaillé')).toBeInTheDocument()
  })

  it('les repliés se déplient au toucher et nomment leurs lignes', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    expect(screen.queryByText('Retour Lydec')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /^En attente/ }))
    expect(screen.getByText('Retour Lydec')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Faites/ }))
    expect(screen.getByText('Dossier subvention')).toBeInTheDocument()
  })

  it('plus de trois activités ERP sans heure : une ligne repliable « n activités ERP »', async () => {
    const d = donnees()
    const activite = d.journee.find((i) => i.type === 'activite')
    d.journee = [d.journee[0], ...[1, 2, 3, 4].map((n) => ({ ...activite, id: 200 + n, titre: `Activité ${n}` }))]
    servir(d)
    monter()
    await screen.findByText('Devis Settat')
    expect(screen.queryByText('Activité 1')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: '4 activités ERP' }))
    expect(screen.getByText('Activité 1')).toBeInTheDocument()
  })
})

describe('TCH76 — états : chargement, erreur, hors ligne, vide', () => {
  it('affiche le squelette seulement après 1 s, jamais avant', async () => {
    vi.useFakeTimers()
    let finir
    servir(() => new Promise((resolu) => { finir = () => resolu({ data: donnees() }) }))
    monter()
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(screen.getByRole('status', { name: 'Chargement' })).toBeInTheDocument()
    await act(async () => { finir(); await vi.advanceTimersByTimeAsync(0) })
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    expect(screen.getByText('Devis Settat')).toBeInTheDocument()
  })

  it('un rafraîchissement en échec GARDE la liste : « Pas à jour · 09:12 » et Réessayer', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    servir(() => Promise.reject(echecReseau()))
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(await screen.findByText('Pas à jour · 09:12')).toBeInTheDocument()
    expect(screen.getByText('Devis Settat')).toBeInTheDocument()
    servir(donnees())
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(screen.queryByText(/Pas à jour/)).toBeNull())
    expect(screen.getByText('Devis Settat')).toBeInTheDocument()
  })

  it('relit au retour du focus', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    expect(api.get).toHaveBeenCalledTimes(1)
    act(() => { window.dispatchEvent(new Event('focus')) })
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('hors ligne : la lecture reste, l\'en-tête le dit, cocher est grisé « Possible une fois connecté »', async () => {
    servir(donnees())
    monter()
    await screen.findByText('Devis Settat')
    api.post.mockClear()
    fixerEnLigne(false)
    expect(screen.getByText(/Hors ligne · dernière synchro à 09:12/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' }))
    expect(api.post).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getAllByRole('status').some((n) => n.textContent.includes('Possible une fois connecté'))).toBe(true))
    expect(screen.getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' })).not.toBeChecked()
  })

  it('aucune tâche : « Colle ou dicte tes listes » et Coller mes listes ouvre la saisie', async () => {
    const d = donnees()
    Object.assign(d, {
      essentiel: [], obligations: [], rendez_vous: [], journee: [], ce_soir: [], a_decider: [], en_attente: [], faites: [],
      a_trier: { boite_reception: 0, bloquees: 0, suggestions: 0, a_convertir: 0 },
      propose: { replie: false, pour_objectif: [], reste_nb: 0, charge: null, suite_par_projet: null },
    })
    servir(d)
    const ouverture = vi.fn()
    window.addEventListener('taqinor:taches:saisir', ouverture)
    monter()
    expect(await screen.findByText('Colle ou dicte tes listes : je les range par projet.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Coller mes listes' }))
    expect(ouverture).toHaveBeenCalledTimes(1)
    window.removeEventListener('taqinor:taches:saisir', ouverture)
  })

  it('rien de gardé, des tâches à trier : la phrase et Trier', async () => {
    const d = donnees()
    Object.assign(d, {
      essentiel: [], obligations: [], rendez_vous: [], journee: [], ce_soir: [], a_decider: [], en_attente: [], faites: [],
      a_trier: { boite_reception: 3, bloquees: 0, suggestions: 0, a_convertir: 0 },
      propose: { replie: false, pour_objectif: [], reste_nb: 0, charge: null, suite_par_projet: null },
    })
    servir(d)
    monter()
    expect(await screen.findByText("Rien de prévu aujourd'hui. 3 tâches attendent dans À trier.")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trier' })).toBeInTheDocument()
  })
})

describe('TCH76 — gestes optimistes', () => {
  it('cocher une tâche : terminer/ part, la ligne reste barrée, le toast propose Annuler', async () => {
    servir(donnees())
    api.post.mockResolvedValue({ data: { ...exempleContrat('taches', 'tache_ecrite'), geste_id: 77, progression: null } })
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Timbres » comme faite' }))
    await waitFor(() => expect(api.post.mock.calls.map((c) => c[0])).toContain('/taches/taches/42/terminer/'))
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('une activité ERP cochée close dans l\'ERP, sans Annuler', async () => {
    const d = donnees()
    d.journee.find((i) => i.type === 'activite').peut_cloturer = true
    servir(d)
    api.post.mockResolvedValue({ data: {} })
    monter()
    await screen.findByText('Devis Settat')
    fireEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Rappeler Benali » comme faite' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/records/activities/101/done/', {}))
    expect(await screen.findByText("Close dans l'ERP")).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Annuler' })).toBeNull()
  })
})
