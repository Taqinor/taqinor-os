import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ROUTE } from '../../../lib/search/entityRoutes'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { EVENEMENT_SAISIR as EVENEMENT_COQUILLE } from '../coquille/CoquilleTaches'
import { reinitialiserGestes } from '../lib/gestes'
import BoutonTachesIci from './BoutonTachesIci'
import { cibleDepuisEcran, ENTITE_DE_CIBLE, EVENEMENT_SAISIR, gabaritDeCible } from './cibleEcran'
import TachesPresence from './TachesPresence'

const mocks = vi.hoisted(() => ({
  listerTaches: vi.fn(), terminerTache: vi.fn(), annulerGeste: vi.fn(), saisieRapide: vi.fn(),
}))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  listerTaches: mocks.listerTaches,
  terminerTache: mocks.terminerTache,
  annulerGeste: mocks.annulerGeste,
  saisieRapide: mocks.saisieRapide,
}))

/* TCH102 — « Créer une tâche depuis ici » : la carte des URL de cibles dit la même chose pour le serveur
   (`liens_cibles.json`), pour l'écran (`cibleDepuisEcran`) et pour la recherche (`entityRoutes.ROUTE`) ;
   l'hôte et le bouton ✓+ n'existent pas sans `taches_voir` ; la saisie reste l'événement unique
   `taqinor:taches:saisir`. Le client répond avec les échantillons du contrat. */

const gabarits = exempleContrat('taches', 'liens_cibles')
const item = exempleContrat('taches', 'item')
const apercu = exempleContrat('taches', 'saisie_apercu')
const creation = exempleContrat('taches', 'saisie_rapide')

const magasin = (permissions) => {
  const etat = { auth: { permissions, role_nom: 'Administrateur', user: { id: 42, active_company_id: 7 } } }
  return { getState: () => etat, subscribe: () => () => {}, dispatch: (a) => a }
}
const monter = (adresse, { permissions = ['taches_voir'], enfants } = {}) => render(
  <Provider store={magasin(permissions)}>
    <MemoryRouter initialEntries={[adresse]}>{enfants ?? <><TachesPresence /><BoutonTachesIci /></>}</MemoryRouter>
  </Provider>,
)
const saisir = (detail = {}) => act(() => { window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail })) })

beforeEach(() => {
  window.localStorage.clear()
  mocks.listerTaches.mockResolvedValue({ data: { count: 1, next: null, results: [{ ...item, id: 20, titre: 'Devis Settat' }] } })
  mocks.terminerTache.mockResolvedValue({ data: { tache: { ...item, statut: 'fait' }, geste_id: 5 } })
  mocks.annulerGeste.mockResolvedValue({ data: {} })
  mocks.saisieRapide.mockImplementation((corps) => Promise.resolve({ data: corps.apercu ? apercu : creation }))
})
afterEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
})

describe('TCH102 — les trois sources des URL de cibles disent la même chose', () => {
  it('chaque gabarit de liens_cibles.json = cibleDepuisEcran = entityRoutes.ROUTE', () => {
    const cibles = Object.keys(gabarits)
    expect(cibles.sort()).toEqual(Object.keys(ENTITE_DE_CIBLE).sort())
    for (const cible of cibles) {
      const gabarit = gabarits[cible]
      // entityRoutes.ROUTE écrit le même gabarit (id → {id})
      expect(ROUTE[ENTITE_DE_CIBLE[cible]]('{id}')).toBe(gabarit)
      expect(gabaritDeCible(cible)).toBe(gabarit)
      // l'inverse : l'URL réelle d'un objet redonne sa cible et son id
      const [pathname, search = ''] = gabarit.replace('{id}', '7').split('?')
      expect(cibleDepuisEcran({ pathname, search: search ? `?${search}` : '' })).toEqual({ cible, id: 7 })
    }
  })

  it('la page de détail d\'un lead (/crm/leads/:id) est aussi reconnue ; une liste nue, un id douteux ou un autre écran, jamais', () => {
    expect(cibleDepuisEcran({ pathname: '/crm/leads/1637', search: '' })).toEqual({ cible: 'crm.lead', id: 1637 })
    expect(cibleDepuisEcran({ pathname: '/crm/leads', search: '' })).toBeNull()
    expect(cibleDepuisEcran({ pathname: '/crm/leads', search: '?lead=abc' })).toBeNull()
    expect(cibleDepuisEcran({ pathname: '/crm/leads', search: '?lead=0' })).toBeNull()
    expect(cibleDepuisEcran({ pathname: '/ventes/factures', search: '?id=3' })).toBeNull()
    expect(cibleDepuisEcran({ pathname: '/stock', search: '' })).toBeNull()
  })

  it('l\'événement de saisie est celui de la coquille, jamais un second mécanisme', () => {
    expect(EVENEMENT_SAISIR).toBe(EVENEMENT_COQUILLE)
    expect(EVENEMENT_SAISIR).toBe('taqinor:taches:saisir')
  })
})

describe('TCH102 — masqué sans le droit taches_voir', () => {
  it('ni bouton, ni feuille, ni requête, ni écoute de « c t » ou de la palette', async () => {
    monter('/crm/leads?lead=9', { permissions: ['crm_voir'] })
    expect(screen.queryByRole('button', { name: /Tâches liées/ })).toBeNull()
    saisir()
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:quick-create', { detail: { type: 'tache' } })) })
    expect(screen.queryByRole('textbox', { name: 'Ajouter une tâche' })).toBeNull()
    expect(mocks.listerTaches).not.toHaveBeenCalled()
  })

  it('un compte sans aucune permission lue n\'a rien non plus (aucun repli)', () => {
    monter('/crm/leads?lead=9', { permissions: [] })
    expect(screen.queryByRole('button', { name: /Tâches liées/ })).toBeNull()
    expect(mocks.listerTaches).not.toHaveBeenCalled()
  })
})

describe('TCH102 — BoutonTachesIci (✓+)', () => {
  it('sur la fiche d\'un lead : une requête filtrée par cible, le compte des ouvertes', async () => {
    monter('/crm/leads?lead=9')
    expect(await screen.findByRole('button', { name: 'Tâches liées à cette fiche (1 ouvertes)' })).toBeInTheDocument()
    expect(mocks.listerTaches).toHaveBeenCalledTimes(1)
    expect(mocks.listerTaches).toHaveBeenCalledWith({ cible: 'crm.lead', cible_id: 9, ouvertes: 1 })
    expect(screen.getByTestId('tch-ici-nb')).toHaveTextContent('1')
  })

  it('hors fiche d\'objet (liste, stock, facture) : pas de bouton, pas de requête', () => {
    monter('/crm/leads')
    expect(screen.queryByRole('button', { name: /Tâches liées/ })).toBeNull()
    expect(mocks.listerTaches).not.toHaveBeenCalled()
  })

  it('une relecture en échec ne vide pas la liste déjà affichée', async () => {
    const user = userEvent.setup()
    monter('/ventes/devis?devis=12')
    await user.click(await screen.findByRole('button', { name: /Tâches liées/ }))
    expect(await screen.findByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' })).toBeInTheDocument()
    mocks.listerTaches.mockRejectedValue(Object.assign(new Error('réseau'), { response: undefined }))
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:taches:creees', { detail: { creees: [] } })) })
    await waitFor(() => expect(mocks.listerTaches).toHaveBeenCalledTimes(3))
    expect(screen.getByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' })).toBeInTheDocument()
    // … et l'écran le DIT : l'erreur du serveur n'est jamais avalée en silence (garde EZ16)
    expect(await screen.findByRole('alert')).toHaveTextContent('Pas à jour')
  })

  it('une PREMIÈRE lecture en échec dit « Pas à jour », jamais « Aucune tâche ouverte liée. »', async () => {
    const user = userEvent.setup()
    mocks.listerTaches.mockRejectedValue(Object.assign(new Error('réseau'), { response: undefined }))
    monter('/ventes/devis?devis=12')
    await user.click(await screen.findByRole('button', { name: 'Tâches liées à cette fiche' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Pas à jour')
    expect(screen.queryByText('Aucune tâche ouverte liée.')).toBeNull()
  })

  it('cocher termine la tâche (optimiste, « Annuler ») et le compte baisse', async () => {
    const user = userEvent.setup()
    monter('/crm?id=4')
    await user.click(await screen.findByRole('button', { name: /Tâches liées/ }))
    await user.click(await screen.findByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    await waitFor(() => expect(mocks.terminerTache).toHaveBeenCalledWith(20))
    await waitFor(() => expect(screen.queryByRole('checkbox', { name: /Devis Settat/ })).toBeNull())
    expect(screen.getByText('Aucune tâche ouverte liée.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tâches liées à cette fiche' })).toBeInTheDocument()
  })

  it('« Nouvelle tâche liée » ouvre LA feuille de saisie avec la puce « Lié à », et la tâche part avec son lien', async () => {
    const user = userEvent.setup()
    monter('/crm/leads?lead=9')
    await user.click(await screen.findByRole('button', { name: /Tâches liées/ }))
    await user.click(screen.getByRole('button', { name: 'Nouvelle tâche liée' }))
    const champ = await screen.findByRole('textbox', { name: 'Ajouter une tâche' })
    expect(screen.getByRole('button', { name: 'Retirer le lien « Lead »' })).toBeInTheDocument()
    await user.type(champ, 'Appeler Karim')
    await screen.findByText('mer. 18 nov.', {}, { timeout: 3000 })
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(mocks.saisieRapide.mock.calls.some(([corps]) => corps.apercu === false)).toBe(true))
    const envoi = mocks.saisieRapide.mock.calls.find(([corps]) => corps.apercu === false)[0]
    expect(envoi.lignes[0].lien).toEqual({ cible: 'crm.lead', id: 9 })
  })
})

describe('TCH102 — hôte TachesPresence', () => {
  it('« c t » sur la fiche d\'un devis ouvre la saisie déjà liée à ce devis, la puce se retire', async () => {
    const user = userEvent.setup()
    monter('/ventes/devis?devis=12', { enfants: <TachesPresence /> })
    expect(screen.queryByRole('textbox', { name: 'Ajouter une tâche' })).toBeNull()
    saisir()
    await screen.findByRole('textbox', { name: 'Ajouter une tâche' })
    await user.click(screen.getByRole('button', { name: 'Retirer le lien « Devis »' }))
    expect(screen.queryByRole('button', { name: /Retirer le lien/ })).toBeNull()
  })

  it('la palette (taqinor:quick-create, type tache) passe par le même événement ; ailleurs, aucune puce de lien', async () => {
    monter('/stock', { enfants: <TachesPresence /> })
    act(() => { window.dispatchEvent(new CustomEvent('taqinor:quick-create', { detail: { type: 'tache' } })) })
    await screen.findByRole('textbox', { name: 'Ajouter une tâche' })
    expect(screen.queryByRole('button', { name: /Retirer le lien/ })).toBeNull()
  })

  it('Acceptation F4 — la phrase envoyée par un écran (Activités) arrive dans la feuille, et l\'hôte répond « reçu »', async () => {
    monter('/activites', { enfants: <TachesPresence /> })
    const evenement = new CustomEvent(EVENEMENT_SAISIR, { cancelable: true, detail: { texte: 'Rappeler le fournisseur', jour_prevu: '2026-11-20' } })
    let recue
    act(() => { recue = !window.dispatchEvent(evenement) })
    // « reçu » : l'écran qui envoie peut vider son champ ; la feuille montre la phrase et le jour
    expect(recue).toBe(true)
    expect(await screen.findByRole('textbox', { name: 'Ajouter une tâche' })).toHaveValue('Rappeler le fournisseur')
    expect(screen.getByRole('button', { name: 'Retirer le jour choisi' })).toBeInTheDocument()
  })

  it('Acceptation F4 — sans hôte qui écoute (pas le droit, ou pas encore chargé), personne ne répond « reçu » : la phrase reste à l\'écran qui l\'envoie', () => {
    monter('/activites', { permissions: ['crm_voir'], enfants: <TachesPresence /> })
    const evenement = new CustomEvent(EVENEMENT_SAISIR, { cancelable: true, detail: { texte: 'Rappeler le fournisseur' } })
    let recue
    act(() => { recue = !window.dispatchEvent(evenement) })
    expect(recue).toBe(false)
  })

  it('dans /taches la coquille a déjà sa feuille : l\'hôte ne monte rien (pas de feuille en double)', () => {
    monter('/taches/aujourdhui', { enfants: <TachesPresence /> })
    saisir()
    expect(screen.queryByRole('textbox', { name: 'Ajouter une tâche' })).toBeNull()
  })
})
