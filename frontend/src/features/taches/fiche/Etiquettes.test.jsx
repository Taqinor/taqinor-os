import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Recherche from '../../../pages/taches/Recherche'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import { reinitialiserGestes } from '../lib/gestes'
import Fiche from './Fiche'

const api = vi.hoisted(() => ({
  lireTache: vi.fn(), modifierTache: vi.fn(), annulerGeste: vi.fn(), creerEtiquette: vi.fn(),
  listerToutesLesEtiquettes: vi.fn(), listerVues: vi.fn(), creerVue: vi.fn(), rechercher: vi.fn(),
  listerTaches: vi.fn(), listerToutesLesTaches: vi.fn(), listerTousLesProjets: vi.fn(),
}))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))

/* TCH166 — Étiquettes dans la fiche (→ Plus) et dans les filtres de la Recherche ; vues enregistrées
   (Enregistrer, rouvrir : une vue rouverte = mêmes filtres). Réponses = `tache.json`, `tache_ecrite.json`,
   `etiquettes.json`, `vues.json`, `projets_liste.json`, `recherche.json` du contrat. */

const tache = exempleContrat('taches', 'tache')
const ecrite = exempleContrat('taches', 'tache_ecrite')
const etiquettes = exempleContrat('taches', 'etiquettes')
const vues = exempleContrat('taches', 'vues')
const projetsListe = exempleContrat('taches', 'projets_liste')
const recherche = exempleContrat('taches', 'recherche')
const AUJOURDHUI = '2026-11-17'
const erreurHttp = (data, status) => Object.assign(new Error('http'), { response: { status, data } })

describe('TCH166 — étiquettes dans la fiche → Plus', () => {
  const monter = () => render(<div className="tch"><Fiche id={20} aujourdhui={AUJOURDHUI} onFermer={vi.fn()} /><ZoneAnnonces /></div>)
  const ouvrirPlus = async (user) => {
    await screen.findByRole('textbox', { name: 'Titre' })
    await user.click(screen.getByRole('button', { name: 'Plus' }))
    await screen.findByRole('button', { name: 'magasin' })
  }
  const puces = () => screen.getByRole('group', { name: 'Étiquettes de la tâche' })

  beforeEach(() => {
    api.lireTache.mockResolvedValue({ data: tache })
    api.modifierTache.mockResolvedValue({ data: ecrite })
    api.annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
    api.listerToutesLesEtiquettes.mockResolvedValue(etiquettes.results)
    api.creerEtiquette.mockResolvedValue({ data: { id: 9, nom: 'urgent', couleur: 'ciel', geste_id: 12 } })
  })
  afterEach(() => {
    vi.clearAllMocks()
    reinitialiserGestes()
  })

  it('montre les étiquettes du compte, celles de la tâche appuyées', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    expect(within(puces()).getByRole('button', { name: 'magasin' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(puces()).getByRole('button', { name: 'appels' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('en poser une : PATCH avec toutes les ids, le toast « Annuler » défait le geste, aucune relecture de liste', async () => {
    const user = userEvent.setup()
    api.modifierTache.mockResolvedValue({ data: { ...ecrite, tache: { ...ecrite.tache, etiquettes: etiquettes.results }, geste_id: 77 } })
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('button', { name: 'appels' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { etiquettes: [2, 3], lock_version: 4 }))
    await waitFor(() => expect(within(puces()).getByRole('button', { name: 'appels' })).toHaveAttribute('aria-pressed', 'true'))
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(77))
    expect(api.listerToutesLesEtiquettes).toHaveBeenCalledTimes(1)
  })

  it('en retirer une : PATCH sans elle', async () => {
    const user = userEvent.setup()
    api.modifierTache.mockResolvedValue({ data: { ...ecrite, tache: { ...ecrite.tache, etiquettes: [] } } })
    monter()
    await ouvrirPlus(user)
    await user.click(screen.getByRole('button', { name: 'magasin' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { etiquettes: [], lock_version: 4 }))
    await waitFor(() => expect(within(puces()).getByRole('button', { name: 'magasin' })).toHaveAttribute('aria-pressed', 'false'))
  })

  it('un nom neuf crée l\'étiquette puis la pose ; un nom connu (casse libre) n\'en crée pas', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirPlus(user)
    const champ = screen.getByRole('textbox', { name: 'Ajouter une étiquette' })
    await user.type(champ, 'urgent{Enter}')
    await waitFor(() => expect(api.creerEtiquette).toHaveBeenCalledWith({ nom: 'urgent' }, { erreurSousLeChamp: true }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenLastCalledWith(20, { etiquettes: [2, 9], lock_version: 4 }))
    expect(champ).toHaveValue('')
    expect(within(puces()).getByRole('button', { name: 'urgent' })).toBeInTheDocument()

    await user.type(champ, 'Appels{Enter}')
    await waitFor(() => expect(api.modifierTache).toHaveBeenLastCalledWith(20, { etiquettes: [2, 3], lock_version: 4 }))
    expect(api.creerEtiquette).toHaveBeenCalledTimes(1)
  })

  it('un nom refusé par le serveur s\'affiche sous le champ, la saisie reste, rien n\'est posé', async () => {
    const user = userEvent.setup()
    api.creerEtiquette.mockRejectedValue(erreurHttp({ nom: ['40 caractères au plus.'] }, 400))
    monter()
    await ouvrirPlus(user)
    const champ = screen.getByRole('textbox', { name: 'Ajouter une étiquette' })
    await user.type(champ, 'urgent{Enter}')
    expect(await screen.findByText('40 caractères au plus.')).toBeInTheDocument()
    expect(champ).toHaveValue('urgent')
    expect(api.modifierTache).not.toHaveBeenCalled()
  })

  it('la liste des étiquettes qui échoue se dit, la fiche reste utilisable', async () => {
    const user = userEvent.setup()
    api.listerToutesLesEtiquettes.mockRejectedValue(erreurHttp({ detail: 'Oups.' }, 500))
    monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    await user.click(screen.getByRole('button', { name: 'Plus' }))
    expect(await screen.findByRole('textbox', { name: 'Ajouter une étiquette' })).toBeInTheDocument()
    expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0)
  })
})

describe('TCH166 — vues enregistrées dans la Recherche', () => {
  const monter = (url = '/taches/recherche?q=devis') => render(
    <MemoryRouter initialEntries={[url]}><Recherche aujourdhui={AUJOURDHUI} /></MemoryRouter>,
  )
  const plusDeFiltres = async (user) => {
    await screen.findByRole('region', { name: /Ouvertes/ })
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
  }

  beforeEach(() => {
    api.rechercher.mockResolvedValue({ data: recherche })
    api.listerTaches.mockResolvedValue({ data: { results: recherche.taches, count: 1, next: null } })
    api.listerToutesLesTaches.mockResolvedValue(recherche.taches)
    api.listerTousLesProjets.mockResolvedValue(projetsListe.results)
    api.listerToutesLesEtiquettes.mockResolvedValue(etiquettes.results)
    api.listerVues.mockResolvedValue({ data: vues })
    api.creerVue.mockImplementation(({ nom, filtres }) => Promise.resolve({ data: { id: 8, nom, rang: 2048, filtres, geste_id: 31 } }))
    api.annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
  })
  afterEach(() => {
    vi.clearAllMocks()
    reinitialiserGestes()
  })

  it('les vues sont lues une fois, à l\'ouverture des filtres repliés', async () => {
    const user = userEvent.setup()
    monter()
    await plusDeFiltres(user)
    expect(await screen.findByRole('button', { name: 'Haute cette semaine' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
    expect(api.listerVues).toHaveBeenCalledTimes(1)
  })

  it('rouvrir une vue pose ses filtres ; l\'enregistrer sous un autre nom rend les mêmes filtres', async () => {
    const user = userEvent.setup()
    monter()
    await plusDeFiltres(user)
    await user.click(await screen.findByRole('button', { name: 'Haute cette semaine' }))
    expect(screen.getByRole('checkbox', { name: 'Priorité haute' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('checkbox', { name: 'Faites aussi' })).toHaveAttribute('aria-checked', 'false')
    expect(await screen.findByRole('button', { name: 'Projet : Ventes ×' })).toBeInTheDocument()
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ projet: 3, priorite_min: 3 })))

    await user.type(screen.getByRole('textbox', { name: 'Nom de la vue' }), 'Copie')
    await user.click(screen.getByRole('button', { name: 'Enregistrer cette vue' }))
    await waitFor(() => expect(api.creerVue).toHaveBeenCalled())
    expect(api.creerVue.mock.calls[0][0]).toEqual({ nom: 'Copie', filtres: vues.results[0].filtres })
  })

  it('enregistrer ce que l\'écran montre : la vue apparaît sans relire la liste, « Annuler » la retire', async () => {
    const user = userEvent.setup()
    monter()
    await plusDeFiltres(user)
    await user.click(screen.getByRole('checkbox', { name: 'Faites aussi' }))
    await user.click(screen.getByRole('checkbox', { name: "Aujourd'hui" }))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tri' }), 'echeance')
    await user.type(screen.getByRole('textbox', { name: 'Nom de la vue' }), 'Mon point{Enter}')
    await waitFor(() => expect(api.creerVue).toHaveBeenCalledWith({
      nom: 'Mon point',
      filtres: { q: 'devis', inclure_faites: true, periode: 'aujourdhui', tri: 'echeance' },
    }, { erreurSousLeChamp: true }))
    expect(await screen.findByRole('button', { name: 'Mon point' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Nom de la vue' })).toHaveValue('')
    expect(api.listerVues).toHaveBeenCalledTimes(1)
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(31))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Mon point' })).toBeNull())
  })

  it('un filtre qui n\'a pas de clé (Plus tard) ne s\'enregistre pas : le bouton est éteint', async () => {
    const user = userEvent.setup()
    monter()
    await plusDeFiltres(user)
    expect(screen.getByRole('button', { name: 'Enregistrer cette vue' })).toBeEnabled()
    await user.click(screen.getByRole('checkbox', { name: 'Plus tard' }))
    expect(screen.getByRole('button', { name: 'Enregistrer cette vue' })).toBeDisabled()
  })

  it('un nom refusé s\'affiche sous le champ et la liste des vues ne bouge pas', async () => {
    const user = userEvent.setup()
    api.creerVue.mockRejectedValue(erreurHttp({ nom: ['Une vue « Haute cette semaine » existe déjà.'] }, 400))
    monter()
    await plusDeFiltres(user)
    await screen.findByRole('button', { name: 'Haute cette semaine' })
    await user.type(screen.getByRole('textbox', { name: 'Nom de la vue' }), 'Haute cette semaine{Enter}')
    expect(await screen.findByText('Une vue « Haute cette semaine » existe déjà.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Haute cette semaine' })).toHaveLength(1)
  })

  it('le filtre Étiquette pose `etiquette` dans la lecture', async () => {
    const user = userEvent.setup()
    monter()
    await plusDeFiltres(user)
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Étiquette' }), '2')
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ etiquette: 2 })))
  })
})
