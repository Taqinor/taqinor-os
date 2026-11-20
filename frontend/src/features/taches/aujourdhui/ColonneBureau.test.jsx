import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

  it('R3-024 — une lecture qui échoue dit « L\'agenda n\'a pas pu être lu » (jamais l\'invite à glisser) et se réessaie', async () => {
    let essais = 0
    servir({ agenda: () => (++essais === 1 ? Promise.reject(new Error('Network Error')) : Promise.resolve({ data: exemple('agenda') })) })
    monter()
    const agenda = await colonne()
    expect(await within(agenda).findByText("L'agenda n'a pas pu être lu")).toBeInTheDocument()
    expect(within(agenda).queryByText('Glisse une tâche sur un créneau pour lui donner une heure.')).toBeNull()
    await userEvent.setup().click(within(agenda).getByRole('button', { name: 'Réessayer' }))
    expect(await within(agenda).findByRole('checkbox', { name: 'Fait : Devis Settat' })).toBeInTheDocument()
    expect(within(agenda).queryByText("L'agenda n'a pas pu être lu")).toBeNull()
    expect(within(agenda).getByText('Glisse une tâche sur un créneau pour lui donner une heure.')).toBeInTheDocument()
  })

  it('R3-024 — les blocs viennent des items de la page (`items`) : l\'agenda lu ne sert que les rendez-vous', async () => {
    const items = exemple('aujourdhui').essentiel // Devis Settat, 10:00 — l'agenda lu, lui, ne le sert plus
    const lu = exemple('agenda')
    lu.jours[0].blocs = []
    servir({ agenda: lu })
    const { rerender } = render(<MemoryRouter><ColonneBureau jour={JOUR} maintenant={MAINTENANT} items={items} /></MemoryRouter>)
    const agenda = await colonne()
    expect(await within(agenda).findByRole('checkbox', { name: 'Fait : Devis Settat' })).toHaveAttribute('aria-checked', 'false')
    expect(within(agenda).getByRole('button', { name: /Réunion banque · 11:00–12:00/ })).toBeInTheDocument()
    rerender(<MemoryRouter><ColonneBureau jour={JOUR} maintenant={MAINTENANT} items={[{ ...items[0], statut: 'fait' }]} /></MemoryRouter>)
    expect(within(agenda).getByRole('checkbox', { name: 'Fait : Devis Settat' })).toHaveAttribute('aria-checked', 'true')
    rerender(<MemoryRouter><ColonneBureau jour={JOUR} maintenant={MAINTENANT} items={[{ ...items[0], jour_prevu: '2026-11-19' }]} /></MemoryRouter>)
    expect(within(agenda).queryByRole('checkbox', { name: 'Fait : Devis Settat' })).toBeNull()
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/agenda/')).toHaveLength(1)
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

  it('F4 revue #7 — glisser sur 14:00, « Annuler », reglisser sur 15:00 : la requête porte la version RENDUE par le serveur', async () => {
    window.matchMedia = media(true)
    const serveur = { verrou: 1 }
    api.post.mockImplementation((url, corps) => {
      if (url === '/taches/taches/42/planifier/') {
        if (corps.lock_version !== serveur.verrou) return Promise.reject(erreurHttp({ code: 'conflit_version', detail: 'Modifiée ailleurs.' }, 409))
        serveur.verrou += 1
        const ecrite = exemple('tache_ecrite')
        return Promise.resolve({ data: { ...ecrite, tache: { ...ecrite.tache, id: 42, heure_debut: corps.heure_debut, lock_version: serveur.verrou }, geste_id: 91 } })
      }
      if (url === '/taches/gestes/91/annuler/') { serveur.verrou += 1; return Promise.resolve({ data: { restaurees: [{ objet: 'tache', id: 42 }], conflits: [], deja: false } }) }
      return Promise.resolve({ data: {} })
    })
    api.get.mockImplementation((url) => {
      if (url === '/taches/taches/42/') return Promise.resolve({ data: { ...exemple('tache_ecrite').tache, id: 42, lock_version: serveur.verrou } })
      if (url === '/taches/agenda/') return Promise.resolve({ data: exemple('agenda') })
      if (url === '/taches/projets/') return Promise.resolve({ data: exemple('projets_liste') })
      if (url === '/taches/aujourdhui/') return Promise.resolve({ data: exemple('aujourdhui') })
      return Promise.reject(new Error(`appel inattendu : GET ${url}`))
    })
    const { container } = monterPage()
    const agenda = await screen.findByRole('complementary', { name: 'Agenda du jour' })
    const ligne = () => container.querySelector('[data-ligne="tache:42"]')
    await waitFor(() => expect(ligne()).not.toBeNull())
    const glisserSur = async (heure) => {
      fireEvent.dragStart(ligne(), { dataTransfer: { setData: vi.fn(), effectAllowed: '' } })
      fireEvent.drop(await within(agenda).findByRole('button', { name: `Placer à ${heure}` }))
    }
    await glisserSur('14:00')
    await waitFor(() => expect(ligne().querySelector('.heure')).toHaveTextContent('14:00'))
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(serveur.verrou).toBe(3))
    await waitFor(() => expect(ligne().querySelector('.heure')).toBeNull())
    await glisserSur('15:00')
    await waitFor(() => expect(api.post.mock.calls.filter(([url]) => url.includes('/planifier/'))).toHaveLength(2))
    expect(api.post.mock.calls.filter(([url]) => url.includes('/planifier/'))[1][1].lock_version).toBe(3)
    await waitFor(() => expect(ligne().querySelector('.heure')).toHaveTextContent('15:00'))
    expect(document.body.textContent).not.toContain('Cette tâche a changé')
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

  it('R2-029 — « Changer de projet… » vers Ventes : le compte de Ventes dans « Mes projets » passe de 8 à 9 sans relire ; Annuler le rend', async () => {
    window.matchMedia = media(true)
    api.post.mockImplementation((url) => Promise.resolve(url === '/taches/taches/lot/'
      ? { data: { geste_id: 95, appliquees: [42], refusees: [] } }
      : url === '/taches/gestes/95/annuler/' ? { data: { restaurees: [{ objet: 'tache', id: 42 }], conflits: [], deja: false } } : { data: {} }))
    monterPage()
    const nav = await screen.findByRole('navigation', { name: 'Mes projets' })
    const ventes = () => within(nav).getByRole('link', { name: /Ventes/ })
    await waitFor(() => expect(ventes()).toHaveTextContent('8'))
    const lectures = api.get.mock.calls.filter(([url]) => url === '/taches/projets/').length
    await userEvent.click(await screen.findByRole('button', { name: 'Actions pour « Timbres »' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Changer de projet…' }))
    const feuille = await screen.findByRole('dialog', { name: 'Changer de projet' })
    await userEvent.click(await within(feuille).findByRole('option', { name: /Ventes/ }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/lot/', expect.objectContaining({ ids: [42], action: 'deplacer' }), expect.anything()))
    expect(ventes()).toHaveTextContent('9')
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(ventes()).toHaveTextContent('8'))
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/projets/').length).toBe(lectures + 1) // la feuille lit la liste ; « Mes projets » ne se relit pas
  })

  it('R3-024 — la colonne SUIT la liste : cocher barre le bloc, la fiche qui change l\'heure ou le jour le déplace, sans relire l\'agenda', async () => {
    window.matchMedia = media(true)
    let lacher
    const porte = new Promise((r) => { lacher = r })
    api.post.mockImplementation((url) => (url === '/taches/taches/20/terminer/'
      ? porte.then(() => ({ data: { ...exemple('tache_ecrite'), tache: { ...exemple('tache_ecrite').tache, id: 20, statut: 'fait', lock_version: 5 } } }))
      : Promise.resolve({ data: {} })))
    monterPage()
    const agenda = await screen.findByRole('complementary', { name: 'Agenda du jour' })
    const bloc = () => within(agenda).queryByRole('checkbox', { name: 'Fait : Devis Settat' })
    await waitFor(() => expect(bloc()).toHaveAttribute('aria-checked', 'false'))
    const lectures = () => api.get.mock.calls.filter(([url]) => url === '/taches/agenda/').length
    const avant = lectures()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    expect(bloc()).toHaveAttribute('aria-checked', 'true') // tout de suite, la réponse est encore retenue
    lacher()
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/20/terminer/', expect.anything()))
    // la fiche (montée par la coquille) a changé l'heure puis le jour : le bloc suit à l'instant
    const { signalerEcrite } = await import('../lib/fiche')
    act(() => signalerEcrite({ ...exemple('tache_ecrite').tache, id: 20, statut: 'a_faire', jour_prevu: JOUR, heure_debut: '15:00', lock_version: 6 }))
    expect(within(agenda).getByRole('checkbox', { name: 'Fait : Devis Settat' }).closest('.bloc')).toHaveTextContent('15:00')
    act(() => signalerEcrite({ ...exemple('tache_ecrite').tache, id: 20, statut: 'a_faire', jour_prevu: '2026-11-19', heure_debut: '15:00', lock_version: 7 }))
    expect(bloc()).toBeNull()
    expect(lectures()).toBe(avant)
  })

  it('une activité ERP ne se glisse pas, une tâche faite non plus', async () => {
    window.matchMedia = media(true)
    const donnees = exemple('aujourdhui')
    donnees.journee = donnees.journee.map((it) => (it.id === 42 ? { ...it, statut: 'fait' } : it))
    servir({ aujourdhui: donnees })
    const { container } = monterPage()
    await waitFor(() => expect(container.querySelector('[data-ligne="tache:20"]')).not.toBeNull()) // le bloc dit aussi « Devis Settat »
    const activite = container.querySelector('[data-ligne^="activite:"]')
    expect(activite).not.toBeNull()
    expect(activite).not.toHaveAttribute('draggable')
    expect(container.querySelector('[data-ligne="tache:42"]')).not.toHaveAttribute('draggable')
    expect(container.querySelector('[data-ligne="tache:20"]')).toHaveAttribute('draggable', 'true')
  })
})
