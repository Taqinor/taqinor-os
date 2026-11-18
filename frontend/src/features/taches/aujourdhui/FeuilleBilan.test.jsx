import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

/* TCH80 — « Bilan du soir » sur journee_cloture.json et journee_cloturee.json : « N sur objectif »
   puis les gardées faites, un choix par reste, Tout reporter, un constat, un mot, Valider ;
   `?ouvrir=bilan` ouvre la feuille ; la veille jusqu'à midi s'appelle « Bilan d'hier ». */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))
const journee = () => {
  const d = contrat('aujourdhui')
  d.carte_du_moment = null
  return d
}

function servir({ cloture = contrat('journee_cloture'), aujourdhui = journee() } = {}) {
  api.get.mockImplementation((url) => {
    if (url === '/taches/aujourdhui/') return Promise.resolve({ data: aujourdhui })
    if (url === '/taches/journee/cloture/') return Promise.resolve({ data: cloture })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
  api.post.mockImplementation((url) => {
    if (url === '/taches/journee/cloturer/') return Promise.resolve({ data: contrat('journee_cloturee') })
    return Promise.resolve({ data: {} })
  })
}

const monter = (url = '/taches/aujourdhui?ouvrir=bilan') => render(
  <MemoryRouter initialEntries={[url]}><Aujourdhui /></MemoryRouter>,
)
const feuille = () => screen.findByRole('dialog', { name: 'Bilan du soir' })
const cloturer = () => api.post.mock.calls.find((c) => c[0] === '/taches/journee/cloturer/')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
  window.localStorage.clear()
  Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true })
})

describe('TCH80 — contenu du bilan', () => {
  it('`?ouvrir=bilan` ouvre la feuille : « 4 sur 5 », les gardées faites, Faites, Reste, Tout reporter', async () => {
    servir()
    monter()
    const f = await feuille()
    expect(await within(f).findByText('4 sur 5')).toBeInTheDocument()
    expect(f).toHaveTextContent('essentiel 1 sur 2')
    expect(f).toHaveTextContent('4 des 5 gardées')
    expect(within(f).getByText('Dossier subvention')).toBeInTheDocument()
    expect(within(f).getByRole('button', { name: 'Tout reporter à jeu. 19' })).toBeInTheDocument()
    const reste = f.querySelector('[data-ligne="tache:42"]')
    expect(within(reste).getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Reporter à jeu. 19', 'Choisir un jour', 'En réserve', 'Abandonner',
    ])
    expect(within(reste).getByRole('button', { name: 'Reporter à jeu. 19' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('une tâche reportée 3 fois est marquée « À revoir » et reste en place sans choix', async () => {
    servir()
    monter()
    const f = await feuille()
    const tranche = await within(f).findByText('Site web')
    const ligne = tranche.closest('[data-ligne]')
    expect(ligne).toHaveTextContent('À revoir : reportée 3 fois')
    expect(f).toHaveTextContent('Sans choix, elle reste à sa place.')
    expect(within(ligne).getByRole('button', { name: 'Reporter à jeu. 19' })).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(within(f).getByRole('button', { name: 'Valider' }))
    await waitFor(() => expect(cloturer()).toBeTruthy())
    expect(cloturer()[1].choix.find((c) => c.id === 50)).toBeUndefined()
  })

  it('les activités ERP du jour sont à clore dans l\'ERP : cocher poste records/activities/{id}/done/', async () => {
    servir()
    monter()
    const f = await feuille()
    expect(await within(f).findByText("À clore dans l'ERP (1)")).toBeInTheDocument()
    fireEvent.click(within(f).getByRole('checkbox', { name: 'Marquer « Rappeler Benali » comme faite' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/records/activities/101/done/', {}))
  })

  it('UN constat au plus, répondu par Oui ou Pas maintenant', async () => {
    servir()
    monter()
    const f = await feuille()
    expect(await within(f).findByText('Vendredi : 3,1 tâches en moyenne, 5,2 les autres jours.')).toBeInTheDocument()
    await userEvent.click(within(f).getByRole('button', { name: 'Oui' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/rythme/propositions/44/repondre/', { reponse: 'oui' }))
    expect(within(f).queryByText(/Vendredi : 3,1/)).toBeNull()
  })

  it('rien à faire : « Tout est fait »', async () => {
    const cloture = contrat('journee_cloture')
    Object.assign(cloture, { restes: [], a_trancher: [], activites_a_clore: [], constat: null })
    servir({ cloture })
    monter()
    expect(await screen.findByText('Tout est fait')).toBeInTheDocument()
  })
})

describe('TCH80 — Valider', () => {
  it('sans toucher : tout est reporté (le_reste) ; Valider ferme, pose « Bilan enregistré · Annuler »', async () => {
    servir()
    monter()
    const f = await feuille()
    await within(f).findByText('Timbres')
    await userEvent.click(within(f).getByRole('button', { name: 'Valider' }))
    await waitFor(() => expect(cloturer()).toBeTruthy())
    expect(cloturer()[1]).toEqual({ jour: '2026-11-17', choix: [], le_reste: true, reflexion: '' })
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Bilan enregistré')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Bilan du soir' })).toBeNull())
  })

  it('un choix par reste : En réserve, un jour choisi, Abandonner ; un mot sur la journée', async () => {
    const cloture = contrat('journee_cloture')
    cloture.restes = [
      cloture.restes[0],
      { ...cloture.restes[0], id: 43, titre: 'Appeler Lydec' },
      { ...cloture.restes[0], id: 44, titre: 'Relire le contrat' },
    ]
    servir({ cloture })
    monter()
    const f = await feuille()
    await within(f).findByText('Appeler Lydec')
    await userEvent.click(within(f.querySelector('[data-ligne="tache:42"]')).getByRole('button', { name: 'En réserve' }))
    await userEvent.click(within(f.querySelector('[data-ligne="tache:44"]')).getByRole('button', { name: 'Abandonner' }))
    await userEvent.click(within(f.querySelector('[data-ligne="tache:43"]')).getByRole('button', { name: 'Choisir un jour' }))
    fireEvent.change(within(f).getByLabelText('Choisir un jour'), { target: { value: '2026-11-23' } })
    await userEvent.click(within(f).getByRole('button', { name: /Un mot sur ta journée/ }))
    await userEvent.type(within(f).getByRole('textbox', { name: 'Un mot sur ta journée' }), 'Bonne journée')
    await userEvent.click(within(f).getByRole('button', { name: 'Valider' }))
    await waitFor(() => expect(cloturer()).toBeTruthy())
    expect(cloturer()[1]).toEqual({
      jour: '2026-11-17',
      choix: [{ id: 42, choix: 'un_jour' }, { id: 43, choix: 'jour', jour: '2026-11-23' }, { id: 44, choix: 'abandonner' }],
      le_reste: true,
      reflexion: 'Bonne journée',
    })
  })

  it('« Tout reporter » remet tous les choix sur le prochain jour travaillé', async () => {
    servir()
    monter()
    const f = await feuille()
    // `waitFor` ne réessaie que si la fonction LÈVE : rendre `null` passait tout de suite quand la ligne n'était pas
    // encore là (échec intermittent sous charge : `within(null)`)
    const reste = await waitFor(() => {
      const ligne = f.querySelector('[data-ligne="tache:42"]')
      expect(ligne).not.toBeNull()
      return ligne
    })
    await userEvent.click(within(reste).getByRole('button', { name: 'Abandonner' }))
    expect(within(reste).getByRole('button', { name: 'Reporter à jeu. 19' })).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(within(f).getByRole('button', { name: 'Tout reporter à jeu. 19' }))
    expect(within(reste).getByRole('button', { name: 'Reporter à jeu. 19' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('Passer ferme sans rien écrire', async () => {
    servir()
    monter()
    const f = await feuille()
    await within(f).findByText('Timbres')
    api.post.mockClear()
    await userEvent.click(within(f).getByRole('button', { name: 'Passer' }))
    expect(screen.queryByRole('dialog', { name: 'Bilan du soir' })).toBeNull()
    expect(cloturer()).toBeUndefined()
  })

  it('hors ligne : Valider est grisé et ne poste rien', async () => {
    servir()
    monter()
    const f = await feuille()
    await within(f).findByText('Timbres')
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
    act(() => { window.dispatchEvent(new Event('offline')) })
    const valider = within(screen.getByRole('dialog', { name: 'Bilan du soir' })).getByRole('button', { name: 'Valider' })
    expect(valider).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(valider)
    expect(cloturer()).toBeUndefined()
  })
})

describe('TCH80 — le bilan d\'hier', () => {
  it('la carte « bilan d\'hier » ouvre le bilan de la veille (jour=…) ; après midi il est en lecture seule', async () => {
    const aujourdhui = journee()
    aujourdhui.carte_du_moment = { type: 'bilan_hier', proposition: null, donnees: { jour: '2026-11-16' } }
    const cloture = contrat('journee_cloture')
    cloture.jour = '2026-11-16'
    servir({ aujourdhui, cloture })
    monter('/taches/aujourdhui')
    await userEvent.click(await screen.findByRole('button', { name: "Faire le bilan d'hier" }))
    const f = await screen.findByRole('dialog', { name: "Bilan d'hier" })
    expect(api.get).toHaveBeenCalledWith('/taches/journee/cloture/', { params: { jour: '2026-11-16' } })
    await within(f).findByText('Timbres')
    expect(f).not.toHaveTextContent('plus modifiable')
  })

  it('après midi le lendemain : « Le bilan d\'hier n\'est plus modifiable après midi. »', async () => {
    const aujourdhui = journee()
    aujourdhui.maintenant = '2026-11-18T12:30:00+01:00'
    servir({ aujourdhui })
    monter()
    const f = await feuille()
    expect(await within(f).findByText("Le bilan d'hier n'est plus modifiable après midi.")).toBeInTheDocument()
    expect(within(f).getByRole('button', { name: 'Valider' })).toHaveAttribute('aria-disabled', 'true')
  })
})
