import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import { reinitialiserGestes } from '../lib/gestes'
import CarteMesTaches from './CarteMesTaches'

const mocks = vi.hoisted(() => ({
  lireAujourdhui: vi.fn(), terminerTache: vi.fn(), rouvrirTache: vi.fn(), annulerGeste: vi.fn(),
}))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({
  ...(await importOriginal()),
  lireAujourdhui: mocks.lireAujourdhui,
  terminerTache: mocks.terminerTache,
  rouvrirTache: mocks.rouvrirTache,
  annulerGeste: mocks.annulerGeste,
}))

/* TCH103 — la carte du cockpit rend `aujourdhui.json` : « {faites} sur {objectif} », trois lignes (l'essentiel
   d'abord), « Ouvrir Aujourd'hui », « Rien de gardé ». Aucun chiffre n'est écrit dans l'écran : tout vient de
   l'échantillon. */

const jour = () => structuredClone(exempleContrat('taches', 'aujourdhui'))

const magasin = (permissions) => {
  const etat = { auth: { permissions, role_nom: 'Administrateur', user: { id: 42, active_company_id: 7 } } }
  return { getState: () => etat, subscribe: () => () => {}, dispatch: (a) => a }
}
function Lieu() {
  const l = useLocation()
  return <p data-testid="lieu">{`${l.pathname}${l.search}`}</p>
}
const monter = (permissions = ['taches_voir']) => render(
  <Provider store={magasin(permissions)}>
    <MemoryRouter initialEntries={['/']}>
      <Routes><Route path="/" element={<><CarteMesTaches /><div className="tch"><ZoneAnnonces /></div></>} /><Route path="*" element={<Lieu />} /></Routes>
    </MemoryRouter>
  </Provider>,
)

beforeEach(() => {
  mocks.lireAujourdhui.mockResolvedValue({ data: jour() })
  mocks.terminerTache.mockResolvedValue({ data: { geste_id: 9, progression: { ...jour().progression, faites: 2 } } })
  mocks.rouvrirTache.mockResolvedValue({ data: {} })
  mocks.annulerGeste.mockResolvedValue({ data: {} })
})
afterEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
})

describe('TCH103 — carte du cockpit « Tâches · Aujourd\'hui »', () => {
  it('« {faites} sur {objectif} », « {n} à faire » (progression servie), trois lignes : essentiel, prévu, puis « Ce soir »', async () => {
    const donnees = jour()
    monter()
    const carte = await screen.findByRole('region', { name: 'Tâches, aujourd\'hui' })
    expect(within(carte).getByText('Tâches · Aujourd\'hui')).toBeInTheDocument()
    expect(carte).toHaveTextContent(`${donnees.progression.faites} sur ${donnees.objectif.nb}`)
    // le nombre « à faire » est celui d'Aujourd'hui : prévues − faites de la progression servie (regles.md §4.9)
    expect(carte).toHaveTextContent(`${donnees.progression.prevues - donnees.progression.faites} à faire`)
    const lignes = within(carte).getAllByRole('listitem')
    expect(lignes).toHaveLength(3)
    // l'essentielle d'abord, puis le prévu (l'activité de l'ERP n'est pas une tâche), puis « Ce soir » (F4 revue #10)
    expect(lignes[0]).toHaveTextContent(donnees.essentiel[0].titre)
    expect(within(lignes[0]).getByRole('img', { name: 'Essentielle' })).toBeInTheDocument()
    expect(lignes[1]).toHaveTextContent(donnees.journee[0].titre)
    expect(lignes[2]).toHaveTextContent(donnees.ce_soir[0].titre)
    expect(carte).not.toHaveTextContent(donnees.faites[0].titre)
  })

  it('F4 revue #10 — avec « Ce soir » seul d\'ouvert, la ligne du soir est montrée et comptée', async () => {
    const donnees = jour()
    donnees.essentiel = []
    donnees.journee = []
    donnees.progression = { ...donnees.progression, faites: 1, prevues: 2 }
    mocks.lireAujourdhui.mockResolvedValue({ data: donnees })
    monter()
    const carte = await screen.findByRole('region', { name: 'Tâches, aujourd\'hui' })
    expect(within(carte).getAllByRole('listitem')[0]).toHaveTextContent(donnees.ce_soir[0].titre)
    expect(carte).toHaveTextContent('1 à faire')
  })

  it('F4 revue #9 — décocher une tâche faite : la case, « {faites} sur {objectif} » et « {n} à faire » suivent (progression rendue)', async () => {
    const donnees = jour()
    donnees.ce_soir = []
    donnees.progression = { ...donnees.progression, faites: 1, prevues: 3 }
    mocks.lireAujourdhui.mockResolvedValue({ data: donnees })
    mocks.rouvrirTache.mockResolvedValue({ data: { progression: { ...donnees.progression, faites: 0, prevues: 3 } } })
    const user = userEvent.setup()
    monter()
    const carte = await screen.findByRole('region', { name: 'Tâches, aujourd\'hui' })
    expect(carte).toHaveTextContent('1 sur 5')
    expect(carte).toHaveTextContent('2 à faire')
    await user.click(within(carte).getByRole('checkbox', { name: `Marquer « ${donnees.faites[0].titre} » comme faite` }))
    await waitFor(() => expect(mocks.rouvrirTache).toHaveBeenCalledWith(12))
    await waitFor(() => expect(carte).toHaveTextContent('0 sur 5'))
    expect(carte).toHaveTextContent('3 à faire')
    within(carte).getAllByRole('checkbox').forEach((case_) => expect(case_).not.toBeChecked())
  })

  it('F4 revue #9 — une réponse sans progression : la carte relit Aujourd\'hui (une fois) au lieu de garder un chiffre périmé', async () => {
    const avant = jour()
    avant.ce_soir = []
    avant.progression = { ...avant.progression, faites: 1, prevues: 3 }
    const apres = structuredClone(avant)
    apres.faites = []
    apres.journee = [...apres.journee, { ...avant.faites[0], statut: 'a_faire' }]
    apres.progression = { ...avant.progression, faites: 0, prevues: 4 }
    mocks.lireAujourdhui.mockResolvedValueOnce({ data: avant }).mockResolvedValue({ data: apres })
    mocks.rouvrirTache.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    monter()
    const carte = await screen.findByRole('region', { name: 'Tâches, aujourd\'hui' })
    await user.click(within(carte).getByRole('checkbox', { name: `Marquer « ${avant.faites[0].titre} » comme faite` }))
    await waitFor(() => expect(carte).toHaveTextContent('0 sur 5'))
    expect(carte).toHaveTextContent('4 à faire')
    expect(mocks.lireAujourdhui).toHaveBeenCalledTimes(2)
  })

  it('cocher une ligne la termine, la progression vient de la réponse du serveur, « Annuler » la rouvre', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(await screen.findByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    await waitFor(() => expect(mocks.terminerTache).toHaveBeenCalledWith(20))
    const carte = screen.getByRole('region', { name: 'Tâches, aujourd\'hui' })
    await waitFor(() => expect(carte).toHaveTextContent('2 sur 5'))
    expect(carte).toHaveTextContent('2 à faire') // prévues 4 − faites 2 : la progression RENDUE par le serveur
    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(mocks.annulerGeste).toHaveBeenCalledWith(9))
    await waitFor(() => expect(carte).toHaveTextContent('1 sur 5'))
  })

  it('« Ouvrir Aujourd\'hui » mène à l\'écran ; le titre d\'une tâche ouvre sa fiche', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(await screen.findByRole('button', { name: 'Ouvrir Aujourd\'hui' }))
    expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/aujourdhui')
  })

  it('le titre d\'une ligne ouvre la fiche de la tâche (?tache=)', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(await screen.findByRole('button', { name: 'Devis Settat' }))
    expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/aujourdhui?tache=20')
  })

  it('rien de gardé : « Rien de gardé », sans ligne', async () => {
    const vide = { ...jour(), essentiel: [], journee: [], ce_soir: [], faites: [], progression: { ...jour().progression, faites: 0 } }
    mocks.lireAujourdhui.mockResolvedValue({ data: vide })
    monter()
    expect(await screen.findByText('Rien de gardé')).toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.getByRole('button', { name: 'Ouvrir Aujourd\'hui' })).toBeInTheDocument()
  })

  it('mode libre : « {faites} faite(s) », sans objectif', async () => {
    const libre = { ...jour(), objectif: { nb: null, source: 'dit', mode: 'libre', zone: null } }
    mocks.lireAujourdhui.mockResolvedValue({ data: libre })
    monter()
    expect(await screen.findByText(`${libre.progression.faites} faite`)).toBeInTheDocument()
  })

  it('sans taches_voir : aucune carte, aucune requête', () => {
    monter(['crm_voir'])
    expect(screen.queryByRole('region', { name: 'Tâches, aujourd\'hui' })).toBeNull()
    expect(mocks.lireAujourdhui).not.toHaveBeenCalled()
  })

  it('lecture en échec : pas de carte, pas de faux chiffre', async () => {
    mocks.lireAujourdhui.mockRejectedValue(new Error('réseau'))
    monter()
    await waitFor(() => expect(mocks.lireAujourdhui).toHaveBeenCalled())
    expect(screen.queryByRole('region', { name: 'Tâches, aujourd\'hui' })).toBeNull()
  })
})
