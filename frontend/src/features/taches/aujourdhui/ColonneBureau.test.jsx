import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import { reinitialiserGestes } from '../lib/gestes'
import ColonneBureau, { ColonneProjets } from './ColonneBureau'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../../api/axios')).default
const { default: Aujourdhui } = await import('../../../pages/taches/Aujourdhui')

/* TCH152 — Aujourd'hui au bureau : l'Agenda du jour à droite (`GrilleAgenda`), « Mes projets » à gauche, glisser une
   ligne sur un créneau pour lui donner une heure (`POST taches/{id}/planifier/`). Réponses = `agenda.json`,
   `projets_liste.json`, `tache_ecrite.json`, `aujourdhui.json` du contrat ; le client HTTP est le seul mock. */

const exemple = (nom) => structuredClone(exempleContrat('taches', nom))
const JOUR = '2026-11-17'
const MAINTENANT = '2026-11-17T09:12:00+01:00'
const erreurHttp = (data, status) => Object.assign(new Error('http'), { response: { status, data } })
const timbres = () => exemple('agenda').jours[0].sans_heure[0]

/** `POST planifier/` rend la tâche posée à `heure`, version suivante, avec son geste annulable. */
function repondrePlanifier(heure, geste = 91) {
  const ecrite = exemple('tache_ecrite')
  return Promise.resolve({
    data: { ...ecrite, tache: { ...ecrite.tache, id: 42, heure_debut: heure, lock_version: 2 }, geste_id: geste },
  })
}

function servir({ agenda = exemple('agenda'), aujourdhui = exemple('aujourdhui') } = {}) {
  api.get.mockImplementation((url) => {
    if (url === '/taches/agenda/') return typeof agenda === 'function' ? agenda() : Promise.resolve({ data: agenda })
    if (url === '/taches/projets/') return Promise.resolve({ data: exemple('projets_liste') })
    if (url === '/taches/aujourdhui/') return Promise.resolve({ data: aujourdhui })
    return Promise.reject(new Error(`appel inattendu : GET ${url}`))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
  servir()
})
afterEach(() => { reinitialiserGestes() })

describe('TCH152 — la colonne Agenda du bureau', () => {
  const monter = (props = {}) => render(
    <MemoryRouter>
      <ColonneBureau jour={JOUR} maintenant={MAINTENANT} {...props} />
      <ZoneAnnonces />
    </MemoryRouter>,
  )
  const colonne = () => screen.findByRole('complementary', { name: 'Agenda du jour' })
  const creneau = (heure) => screen.getByRole('button', { name: `Placer à ${heure}` })

  it('lit l\'agenda du jour et le montre : « Toute la journée », les blocs à heure, les rendez-vous, l\'aide', async () => {
    monter()
    const agenda = await colonne()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/taches/agenda/', { params: { du: JOUR, au: JOUR } }))
    expect(within(agenda).getByText('Agenda')).toBeInTheDocument()
    expect(await within(agenda).findByRole('link', { name: 'Visite — Karim Benali' })).toHaveAttribute('href', '/visites')
    expect(within(agenda).getByRole('checkbox', { name: 'Fait : Devis Settat' })).toBeInTheDocument()
    expect(within(agenda).getByRole('button', { name: /Réunion banque · 11:00–12:00 · Microsoft 365/ })).toBeInTheDocument()
    expect(within(agenda).getByText('Glisse une tâche sur un créneau pour lui donner une heure.')).toBeInTheDocument()
    expect(within(agenda).getByRole('button', { name: 'Ajouter à 10:00' })).toBeInTheDocument()
  })

  it('glisser une ligne sur un créneau appelle planifier/ avec le jour, l\'heure et la version ; le bloc apparaît et « Annuler » le retire', async () => {
    api.post.mockImplementation((url) => (url === '/taches/taches/42/planifier/' ? repondrePlanifier('14:00') : Promise.resolve({ data: {} })))
    const surPlacee = vi.fn()
    const surRetiree = vi.fn()
    const item = timbres()
    monter({ glisse: item, onPlacee: surPlacee, onRetiree: surRetiree })
    const agenda = await colonne()
    await within(agenda).findByRole('checkbox', { name: 'Fait : Devis Settat' })
    expect(within(agenda).queryByRole('checkbox', { name: 'Fait : Timbres' })).toBeNull()

    fireEvent.dragOver(creneau('14:00'))
    fireEvent.drop(creneau('14:00'))

    // optimiste : le bloc est déjà là ; le serveur reçoit le jour, l'heure et la version de la ligne
    expect(await within(agenda).findByRole('checkbox', { name: 'Fait : Timbres' })).toBeInTheDocument()
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/42/planifier/', {
      jour_prevu: JOUR, heure_debut: '14:00', moment: '', quelque_jour: false, lock_version: item.lock_version,
    }))
    await waitFor(() => expect(surPlacee).toHaveBeenCalledTimes(1))
    expect(surPlacee.mock.calls[0][0].id).toBe(42)
    expect(surPlacee.mock.calls[0][2]).toBe('14:00')
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(toast).toHaveTextContent('Placée à 14:00')
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/agenda/')).toHaveLength(1) // aucune relecture

    await userEvent.setup().click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/gestes/91/annuler/', {}))
    await waitFor(() => expect(within(agenda).queryByRole('checkbox', { name: 'Fait : Timbres' })).toBeNull())
    expect(surRetiree).toHaveBeenCalledWith(expect.objectContaining({ id: 42 }))
  })

  it('sans glisser, les créneaux ne déposent rien : « Ajouter à {HH:MM} », aucun appel', async () => {
    monter()
    const agenda = await colonne()
    const vide = await within(agenda).findByRole('button', { name: 'Ajouter à 14:00' })
    fireEvent.drop(vide)
    expect(api.post).not.toHaveBeenCalled()
  })

  it('un refus de version : l\'agenda revient comme avant, « Cette tâche a changé : rien n\'a été modifié. »', async () => {
    api.post.mockRejectedValue(erreurHttp({
      detail: 'Modifiée ailleurs.', code: 'conflit_version', lock_version: 5, actuel: { id: 42 },
    }, 409))
    const surPlacee = vi.fn()
    monter({ glisse: timbres(), onPlacee: surPlacee })
    const agenda = await colonne()
    await within(agenda).findByRole('checkbox', { name: 'Fait : Devis Settat' })
    fireEvent.drop(creneau('14:00'))
    await waitFor(() => expect(document.querySelector('.annonce')).toHaveTextContent("Cette tâche a changé : rien n'a été modifié."))
    expect(within(agenda).queryByRole('checkbox', { name: 'Fait : Timbres' })).toBeNull()
    expect(surPlacee).not.toHaveBeenCalled()
  })

  it('un autre refus se dit sous la grille et remet l\'agenda comme avant', async () => {
    api.post.mockRejectedValue(erreurHttp({ detail: 'Oups.' }, 500))
    monter({ glisse: timbres() })
    const agenda = await colonne()
    await within(agenda).findByRole('checkbox', { name: 'Fait : Devis Settat' })
    fireEvent.drop(creneau('14:00'))
    expect(await within(agenda).findByRole('alert')).toBeInTheDocument()
    expect(within(agenda).queryByRole('checkbox', { name: 'Fait : Timbres' })).toBeNull()
  })

  it('une lecture qui échoue dit « Pas à jour » et se réessaie sans masquer le reste', async () => {
    let essais = 0
    servir({ agenda: () => (++essais === 1 ? Promise.reject(new Error('Network Error')) : Promise.resolve({ data: exemple('agenda') })) })
    monter()
    const agenda = await colonne()
    expect(await within(agenda).findByText('Pas à jour · 09:12')).toBeInTheDocument()
    await userEvent.setup().click(within(agenda).getByRole('button', { name: 'Réessayer' }))
    expect(await within(agenda).findByRole('checkbox', { name: 'Fait : Devis Settat' })).toBeInTheDocument()
    expect(within(agenda).queryByText(/Pas à jour/)).toBeNull()
  })
})

describe('TCH152 — la colonne Mes projets', () => {
  it('une ligne par projet avec le nombre de tâches ouvertes du serveur, qui mène au projet', async () => {
    render(<MemoryRouter><ColonneProjets /></MemoryRouter>)
    const nav = await screen.findByRole('navigation', { name: 'Mes projets' })
    const projet = exemple('projets_liste').results[0]
    const lien = within(nav).getByRole('link', { name: new RegExp(projet.nom) })
    expect(lien).toHaveAttribute('href', `/taches/projets/${projet.id}`)
    expect(lien).toHaveTextContent(String(projet.compteurs.ouvertes))
  })

  it('sans projet, rien n\'est montré', async () => {
    api.get.mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } })
    render(<MemoryRouter><ColonneProjets /></MemoryRouter>)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(screen.queryByRole('navigation', { name: 'Mes projets' })).toBeNull()
  })
})

describe('TCH152 — la page Aujourd\'hui, au bureau et sur iPhone', () => {
  const ancienne = window.matchMedia
  const media = (bureau) => vi.fn().mockImplementation((requete) => ({
    matches: bureau, media: requete, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }))
  afterEach(() => { window.matchMedia = ancienne })
  const monterPage = () => render(<MemoryRouter initialEntries={['/taches/aujourdhui']}><Aujourdhui /></MemoryRouter>)

  it('iPhone : la liste seule, aucune colonne, aucune lecture d\'agenda', async () => {
    window.matchMedia = media(false)
    monterPage()
    await screen.findByText('Devis Settat')
    expect(screen.queryByRole('complementary', { name: 'Agenda du jour' })).toBeNull()
    expect(screen.queryByRole('navigation', { name: 'Mes projets' })).toBeNull()
    expect(api.get.mock.calls.some(([url]) => url === '/taches/agenda/')).toBe(false)
  })

  it('bureau : l\'Agenda à droite, Mes projets à gauche ; glisser « Timbres » sur 14:00 lui donne son heure, sans relire la journée', async () => {
    window.matchMedia = media(true)
    api.post.mockImplementation((url) => (url === '/taches/taches/42/planifier/' ? repondrePlanifier('14:00') : Promise.resolve({ data: {} })))
    const { container } = monterPage()
    const agenda = await screen.findByRole('complementary', { name: 'Agenda du jour' })
    expect(await screen.findByRole('navigation', { name: 'Mes projets' })).toBeInTheDocument()
    const ligne = await waitFor(() => {
      const trouvee = container.querySelector('[data-ligne="tache:42"]')
      expect(trouvee).not.toBeNull()
      return trouvee
    })
    expect(ligne).toHaveAttribute('draggable', 'true')
    expect(ligne.querySelector('.heure')).toBeNull()
    const lectures = api.get.mock.calls.filter(([url]) => url === '/taches/aujourdhui/').length

    fireEvent.dragStart(ligne, { dataTransfer: { setData: vi.fn(), effectAllowed: '' } })
    fireEvent.drop(await within(agenda).findByRole('button', { name: 'Placer à 14:00' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/42/planifier/', expect.objectContaining({
      jour_prevu: JOUR, heure_debut: '14:00', lock_version: 1,
    })))
    await waitFor(() => expect(container.querySelector('[data-ligne="tache:42"] .heure')).toHaveTextContent('14:00'))
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/aujourdhui/')).toHaveLength(lectures)
    // le dépôt ferme les créneaux même si la ligne glissée a changé de place (aucun `dragend` ne lui parvient)
    expect(await within(agenda).findByRole('button', { name: 'Ajouter à 14:00' })).toBeInTheDocument()
  })

  it('un glisser abandonné (aucun dépôt) referme les créneaux et n\'écrit rien', async () => {
    window.matchMedia = media(true)
    const { container } = monterPage()
    const agenda = await screen.findByRole('complementary', { name: 'Agenda du jour' })
    const ligne = await waitFor(() => {
      const trouvee = container.querySelector('[data-ligne="tache:42"]')
      expect(trouvee).not.toBeNull()
      return trouvee
    })
    fireEvent.dragStart(ligne, { dataTransfer: { setData: vi.fn(), effectAllowed: '' } })
    expect(await within(agenda).findByRole('button', { name: 'Placer à 14:00' })).toBeInTheDocument()
    fireEvent.dragEnd(ligne)
    expect(await within(agenda).findByRole('button', { name: 'Ajouter à 14:00' })).toBeInTheDocument()
    expect(api.post.mock.calls.some(([url]) => url.includes('/planifier/'))).toBe(false)
  })

  it('une activité ERP ne se glisse pas, une tâche faite non plus', async () => {
    window.matchMedia = media(true)
    const donnees = exemple('aujourdhui')
    donnees.journee = donnees.journee.map((it) => (it.id === 42 ? { ...it, statut: 'fait' } : it))
    servir({ aujourdhui: donnees })
    const { container } = monterPage()
    await screen.findByText('Devis Settat')
    const activite = container.querySelector('[data-ligne^="activite:"]')
    expect(activite).not.toBeNull()
    expect(activite).not.toHaveAttribute('draggable')
    expect(container.querySelector('[data-ligne="tache:42"]')).not.toHaveAttribute('draggable')
    expect(container.querySelector('[data-ligne="tache:20"]')).toHaveAttribute('draggable', 'true')
  })
})
