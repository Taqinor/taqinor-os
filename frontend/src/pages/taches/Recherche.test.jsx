import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import Recherche from './Recherche'
import Supprimees from './Supprimees'

const api = vi.hoisted(() => ({
  rechercher: vi.fn(), listerTaches: vi.fn(), listerToutesLesTaches: vi.fn(), listerTousLesProjets: vi.fn(), listerToutesLesEtiquettes: vi.fn(),
  listerSupprimees: vi.fn(), listerGestes: vi.fn(), restaurerProjet: vi.fn(), restaurerTache: vi.fn(), annulerGeste: vi.fn(),
  terminerTache: vi.fn(), rouvrirTache: vi.fn(), supprimerTache: vi.fn(),
}))
vi.mock('../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))

/* TCH87 — Recherche (deux groupes Ouvertes/Faites, filtres visibles et repliés, tri, vide) et
   Supprimées récemment (un projet = une ligne, Restaurer, Derniers gestes). Réponses = `recherche.json`,
   `supprimees.json`, `gestes.json` du contrat. */

const recherche = exempleContrat('taches', 'recherche')
const supprimees = exempleContrat('taches', 'supprimees')
const gestes = exempleContrat('taches', 'gestes')
const etiquettes = exempleContrat('taches', 'etiquettes')
const projetsListe = exempleContrat('taches', 'projets_liste')
const AUJOURD = '2026-11-17'
const erreurHttp = (data, status) => Object.assign(new Error('http'), { response: { status, data } })

const item = (id, titre, plus = {}) => ({ ...recherche.taches[0], id, titre, ...plus })
const MIXTE = {
  projets: recherche.projets,
  taches: [
    item(20, 'Devis Settat'),
    item(21, 'Déclaration TVA', { jour_prevu: null, echeance: null, priorite: 3 }),
    item(12, 'Dossier subvention', { statut: 'fait' }),
  ],
}

const monter = (url = '/taches/recherche?q=devis') => render(
  <MemoryRouter initialEntries={[url]}><Recherche aujourdhui={AUJOURD} /></MemoryRouter>,
)

beforeEach(() => {
  api.rechercher.mockResolvedValue({ data: MIXTE })
  api.listerTaches.mockResolvedValue({ data: { results: MIXTE.taches, count: 3, next: null } })
  api.listerToutesLesTaches.mockResolvedValue(MIXTE.taches)
  api.listerTousLesProjets.mockResolvedValue(projetsListe.results)
  api.listerToutesLesEtiquettes.mockResolvedValue(etiquettes.results)
  api.listerSupprimees.mockResolvedValue({ data: supprimees })
  api.listerGestes.mockResolvedValue({ data: gestes })
  api.restaurerProjet.mockResolvedValue({ data: {} })
  api.restaurerTache.mockResolvedValue({ data: { tache: { ...supprimees.taches[0].item } } })
  api.annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
})
afterEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
})

describe('TCH87 — Recherche', () => {
  it('deux groupes « Ouvertes (n) » puis « Faites (n) », et les projets trouvés', async () => {
    monter()
    expect(await screen.findByRole('region', { name: 'Ouvertes (2)' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Faites (1)' })).toBeInTheDocument()
    expect(api.rechercher).toHaveBeenCalledWith({ q: 'devis', limite: 25 })
    expect(screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' })).toHaveValue('devis')
    const projets = screen.getByRole('list', { name: 'Projets trouvés' })
    expect(within(projets).getByText('Ventes')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Faites (1)' })).getByText('Dossier subvention')).toBeInTheDocument()
  })

  it('rien pour « {q} » : la phrase, sans groupes', async () => {
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [] } })
    monter('/taches/recherche?q=zzz')
    expect(await screen.findByText('Rien pour « zzz »')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /Ouvertes/ })).toBeNull()
  })

  it('sans mot ni filtre, rien n\'est demandé au serveur', async () => {
    monter('/taches/recherche')
    await screen.findByRole('searchbox', { name: 'Chercher dans mes tâches' })
    expect(api.rechercher).not.toHaveBeenCalled()
    expect(api.listerTaches).not.toHaveBeenCalled()
  })

  it('taper garde le texte tel quel et relance la recherche après la pause', async () => {
    const user = userEvent.setup()
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [] } })
    monter('/taches/recherche')
    await user.type(screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' }), 'Karim  é')
    expect(screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' })).toHaveValue('Karim  é')
    await waitFor(() => expect(api.rechercher).toHaveBeenLastCalledWith({ q: 'Karim  é', limite: 25 }))
  })

  it('Faites aussi et Priorité haute passent par la liste paginée avec les filtres de l\'API', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('checkbox', { name: 'Faites aussi' }))
    await user.click(screen.getByRole('checkbox', { name: 'Priorité haute' }))
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'devis', inclure_faites: true, priorite_min: 3 })))
    expect(await screen.findByRole('region', { name: 'Faites (1)' })).toBeInTheDocument()
  })

  it('Projet ▾ : le sélecteur choisit le projet, la puce le dit, un 2e toucher l\'enlève', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('button', { name: 'Projet ▾' }))
    await user.click(await screen.findByRole('option', { name: 'Ventes' }))
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ projet: 3 })))
    expect(await screen.findByRole('button', { name: 'Projet : Ventes ×' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Projet : Ventes ×' }))
    expect(await screen.findByRole('button', { name: 'Projet ▾' })).toBeInTheDocument()
  })

  it('filtres repliés : « Sans date » ne garde que les lignes sans jour ; Étiquette ▾ et le tri sont là', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    expect(screen.queryByRole('checkbox', { name: 'Sans date' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
    await user.click(screen.getByRole('checkbox', { name: 'Sans date' }))
    expect(screen.getByRole('region', { name: 'Ouvertes (1)' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Ouvertes (1)' })).getByText('Déclaration TVA')).toBeInTheDocument()
    expect(await screen.findByRole('option', { name: 'magasin' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Tri' })).toHaveValue('manuel')
    // « En réserve » est une vue du serveur
    await user.click(screen.getByRole('checkbox', { name: 'En réserve' }))
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ vue: 'quelque_jour' })))
  })

  it('Raccord F2 — « Aujourd\'hui » et « 7 jours » passent par `periode` du serveur, le tri servi suit', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
    await user.click(screen.getByRole('checkbox', { name: '7 jours' }))
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'devis', periode: 'semaine' })))
    await user.click(screen.getByRole('checkbox', { name: "Aujourd'hui" }))
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ periode: 'aujourdhui' })))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tri' }), 'echeance')
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ periode: 'aujourdhui', tri: 'echeance' })))
  })

  it('Raccord F2 — étiquettes pas encore servies (501) : ni erreur ni filtre Étiquette', async () => {
    const user = userEvent.setup()
    api.listerToutesLesEtiquettes.mockRejectedValue(erreurHttp({ detail: 'Pas encore.' }, 501))
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
    await waitFor(() => expect(api.listerToutesLesEtiquettes).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('combobox', { name: 'Étiquette' })).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('Raccord F2 — une tâche abandonnée (statut `annule`) n\'est pas rangée dans Ouvertes', async () => {
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [item(20, 'Devis Settat'), item(30, 'Devis abandonné', { statut: 'annule' })] } })
    monter()
    expect(await screen.findByRole('region', { name: 'Ouvertes (1)' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Ouvertes (1)' })).queryByText('Devis abandonné')).toBeNull()
  })

  it('Raccord F2 — une ligne ouvre la fiche (`?tache=`) ; la croix la ferme par le retour, l\'écran reste tel quel', async () => {
    const user = userEvent.setup()
    vi.spyOn(console, 'error').mockImplementation(() => {})
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('button', { name: 'Devis Settat' }))
    const fiche = await screen.findByRole('dialog')
    await user.click(within(fiche).getByRole('button', { name: 'Fermer' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' })).toHaveValue('devis')
    expect(screen.getByRole('region', { name: 'Ouvertes (2)' })).toBeInTheDocument()
  })

  it('tri par priorité : la plus haute d\'abord', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tri' }), 'priorite')
    const ouvertes = within(screen.getByRole('region', { name: 'Ouvertes (2)' })).getAllByRole('listitem')
    expect(ouvertes[0]).toHaveTextContent('Déclaration TVA')
  })

  it('une lecture en échec garde la dernière liste et le dit', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    api.rechercher.mockRejectedValue(erreurHttp({ detail: 'Erreur du serveur.' }, 500))
    await user.type(screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' }), 's')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Ouvertes (2)' })).toBeInTheDocument()
  })

  it('cocher une ligne la termine (toast « Faite · Annuler »)', async () => {
    const user = userEvent.setup()
    api.terminerTache.mockResolvedValue({ data: { tache: { ...MIXTE.taches[0], statut: 'fait' }, geste_id: 9 } })
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    await waitFor(() => expect(api.terminerTache).toHaveBeenCalledWith(20, {}))
    expect(await screen.findByRole('region', { name: 'Faites (2)' })).toBeInTheDocument()
  })
})

describe('TCH87 — Supprimées récemment', () => {
  const monterSupprimees = () => render(<MemoryRouter><Supprimees /></MemoryRouter>)

  it('un projet = une ligne « « {projet} » et ses {n} tâches », la tâche seule, les derniers gestes', async () => {
    monterSupprimees()
    expect(await screen.findByText('« Ancien salon » et ses 25 tâches')).toBeInTheDocument()
    expect(screen.getByText('Supprimées depuis moins de 30 jours.')).toBeInTheDocument()
    expect(screen.getByText('Timbres')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Derniers gestes' })).toHaveTextContent('Reportée à jeu. 19')
  })

  it('Restaurer un projet : la ligne part ; 409 nom_pris : « Un projet actif porte déjà ce nom. » sous la ligne', async () => {
    const user = userEvent.setup()
    api.restaurerProjet.mockRejectedValueOnce(erreurHttp(exempleContrat('taches', 'erreurs').nom_pris, 409))
    monterSupprimees()
    await user.click(await screen.findByRole('button', { name: 'Restaurer « Ancien salon »' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Un projet actif porte déjà ce nom.')
    expect(screen.getByText('« Ancien salon » et ses 25 tâches')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Restaurer « Ancien salon »' }))
    await waitFor(() => expect(screen.queryByText('« Ancien salon » et ses 25 tâches')).toBeNull())
    expect(api.restaurerProjet).toHaveBeenLastCalledWith(11)
  })

  it('Restaurer une tâche dont le projet a disparu : « Restaurée dans À trier »', async () => {
    const user = userEvent.setup()
    api.listerSupprimees.mockResolvedValue({ data: { projets: [], taches: [{ ...supprimees.taches[0], item: { ...supprimees.taches[0].item, projet: { id: 9, nom: 'Parti', couleur: 'vert', priorite: 1 } } }] } })
    api.restaurerTache.mockResolvedValue({ data: { tache: { ...supprimees.taches[0].item, projet: null } } })
    monterSupprimees()
    await user.click(await screen.findByRole('button', { name: 'Restaurer « Timbres »' }))
    await waitFor(() => expect(api.restaurerTache).toHaveBeenCalledWith(42))
    expect(await screen.findByText('Rien de supprimé')).toBeInTheDocument()
  })

  it('Derniers gestes : Annuler défait le geste ; un geste déjà annulé dit « Déjà annulé »', async () => {
    const user = userEvent.setup()
    api.listerGestes.mockResolvedValue({ data: { results: [
      ...gestes.results,
      { id: 78, type: 'lot', message: 'Supprimée', created_at: '2026-11-16T10:00:00+01:00', annule_le: '2026-11-16T10:05:00+01:00', annulable: false },
    ] } })
    monterSupprimees()
    const section = await screen.findByRole('region', { name: 'Derniers gestes' })
    expect(within(section).getByText('Déjà annulé')).toBeInTheDocument()
    await user.click(within(section).getByRole('button', { name: 'Annuler : Reportée à jeu. 19' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(77))
    expect(await screen.findByRole('status')).toBeDefined()
  })

  it('rien de supprimé : la phrase, et une lecture en échec ne fait pas croire à une liste vide', async () => {
    api.listerSupprimees.mockResolvedValue({ data: { projets: [], taches: [] } })
    api.listerGestes.mockResolvedValue({ data: { results: [] } })
    const { unmount } = monterSupprimees()
    expect(await screen.findByText('Rien de supprimé')).toBeInTheDocument()
    unmount()
    api.listerSupprimees.mockRejectedValue(erreurHttp({ detail: 'Erreur du serveur.' }, 500))
    monterSupprimees()
    await screen.findByRole('alert')
    expect(screen.queryByText('Rien de supprimé')).toBeNull()
  })
})
