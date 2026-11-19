import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import Recherche from './Recherche'
import Supprimees from './Supprimees'

const api = vi.hoisted(() => ({
  rechercher: vi.fn(), listerTaches: vi.fn(), listerToutesLesTaches: vi.fn(), listerTousLesProjets: vi.fn(), listerToutesLesEtiquettes: vi.fn(), listerVues: vi.fn(),
  listerSupprimees: vi.fn(), listerGestes: vi.fn(), restaurerProjet: vi.fn(), restaurerTache: vi.fn(), annulerGeste: vi.fn(),
  terminerTache: vi.fn(), rouvrirTache: vi.fn(), supprimerTache: vi.fn(), lireTache: vi.fn(),
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

// une autre tâche que la 20 du contrat (qui porte une note) n'a pas de note : `a_notes` faux par défaut
const item = (id, titre, plus = {}) => ({ ...recherche.taches[0], a_notes: false, id, titre, ...plus })
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
  api.listerVues.mockResolvedValue({ data: exempleContrat('taches', 'vues') }) // TCH166 : lues à l'ouverture des filtres repliés
  api.listerSupprimees.mockResolvedValue({ data: supprimees })
  api.listerGestes.mockResolvedValue({ data: gestes })
  api.restaurerProjet.mockResolvedValue({ data: {} })
  api.restaurerTache.mockResolvedValue({ data: { tache: { ...supprimees.taches[0].item } } })
  api.annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
  api.lireTache.mockRejectedValue(new Error('Network Error')) // comme avant : aucun serveur derrière la fiche
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

  it('passe visuelle n° 46 — la loupe est DANS le champ (recherche.html), champ et filtres dans la rangée alignée', async () => {
    monter()
    const champ = screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' })
    const boite = champ.closest('label.es-champ')
    expect(boite).not.toBeNull()
    expect(boite.querySelector('svg')).not.toBeNull()
    expect(boite.closest('.es-recherche')).not.toBeNull()
    expect(screen.getByLabelText('Filtres')).toHaveClass('es-filtres')
  })

  it('passe visuelle n° 46 — le mot cherché est surligné dans chaque résultat, qui porte sa méta de statut', async () => {
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [
      item(30, 'Préparer le chantier du devis accepté', { jour_prevu: null, heure_debut: null, projet: null, echeance: null, source: 'suggestion' }),
      item(31, 'Comparer deux Devis', { jour_prevu: null, heure_debut: null, quelque_jour: true, echeance: null }),
    ] } })
    monter()
    const ouvertes = await screen.findByRole('region', { name: 'Ouvertes (2)' })
    expect([...ouvertes.querySelectorAll('.titre b.es-trouve')].map((b) => b.textContent)).toEqual(['devis', 'Devis'])
    const metas = [...ouvertes.querySelectorAll('.meta')].map((m) => [...m.children].map((e) => e.textContent))
    expect(metas).toEqual([['À trier', "Suggéré par l'ERP"], ['En réserve', 'Ventes']])
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

  it('Projet : le sélecteur choisit le projet, la puce le dit, un 2e toucher l\'enlève', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('button', { name: 'Projet' }))
    await user.click(await screen.findByRole('option', { name: 'Ventes' }))
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ projet: 3 })))
    expect(await screen.findByRole('button', { name: 'Projet : Ventes ×' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Projet : Ventes ×' }))
    expect(await screen.findByRole('button', { name: 'Projet' })).toBeInTheDocument()
  })

  it('R2-124 — « Faites cette semaine » (puce visible) : les faites depuis lundi, par jour, le plus récent en haut, compte par jour', async () => {
    const user = userEvent.setup()
    const faite = (id, titre, faitLe) => item(id, titre, { statut: 'fait', fait_le: faitLe, jour_prevu: null, heure_debut: null })
    // le serveur sert la plus récemment faite d'abord (`tri` fait_le par défaut sous `periode=faites_semaine`)
    const semaine = [
      faite(40, 'Rappeler Lydec', '2026-11-19T16:10:00Z'), faite(41, 'Devis Settat', '2026-11-19T09:05:00Z'),
      faite(42, 'Timbres', '2026-11-18T11:00:00Z'), faite(43, 'Dossier subvention', '2026-11-17T08:30:00Z'),
    ]
    api.listerTaches.mockResolvedValue({ data: { results: semaine, count: 4, next: null } })
    render(<MemoryRouter initialEntries={['/taches/recherche']}><Recherche aujourdhui="2026-11-19" /></MemoryRouter>)
    // visible sans déplier « Plus de filtres » : Aujourd'hui → loupe → cette puce
    const puce = within(screen.getByLabelText('Filtres')).getByRole('checkbox', { name: 'Faites cette semaine' })
    await user.click(puce)
    await waitFor(() => expect(api.listerTaches).toHaveBeenLastCalledWith(expect.objectContaining({ periode: 'faites_semaine' })))
    expect(puce).toHaveAttribute('aria-checked', 'true')
    const regions = await screen.findAllByRole('region')
    expect(regions.map((r) => r.getAttribute('aria-label'))).toEqual(["Aujourd'hui (2)", 'Hier (1)', 'mar. 17 (1)'])
    expect(within(regions[0]).getAllByRole('listitem').map((l) => l.textContent)).toEqual([
      expect.stringContaining('Rappeler Lydec'), expect.stringContaining('Devis Settat')])
    expect(screen.getByText('4 faites depuis lundi')).toHaveClass('es-sous')
    expect(screen.queryByRole('region', { name: /Ouvertes/ })).toBeNull()
    // un 2e toucher la retire : retour à la recherche ordinaire, rien demandé sans mot
    await user.click(puce)
    expect(puce).toHaveAttribute('aria-checked', 'false')
  })

  it('R2-124 — l\'adresse garde la vue (`?periode=faites_semaine`) ; rien de fait : la phrase le dit', async () => {
    api.listerTaches.mockResolvedValue({ data: { results: [], count: 0, next: null } })
    monter('/taches/recherche?periode=faites_semaine')
    expect(await screen.findByText('Rien de fait depuis lundi')).toBeInTheDocument()
    expect(api.listerTaches).toHaveBeenCalledWith(expect.objectContaining({ periode: 'faites_semaine' }))
    expect(screen.getByRole('checkbox', { name: 'Faites cette semaine' })).toHaveAttribute('aria-checked', 'true')
  })

  it('R2-129 — le curseur est dans le champ à l\'ouverture : on tape directement', async () => {
    monter('/taches/recherche')
    const champ = await screen.findByRole('searchbox', { name: 'Chercher dans mes tâches' })
    await waitFor(() => expect(champ).toHaveFocus()) // pris APRÈS le focus que l'ERP pose sur le contenu à chaque navigation
  })

  it('R2-129 — si l\'ERP déplace le focus sur la zone de contenu juste après l\'ouverture, le champ le reprend', async () => {
    const contenu = document.createElement('main')
    contenu.id = 'contenu'
    contenu.tabIndex = -1
    document.body.appendChild(contenu)
    try {
      monter('/taches/recherche')
      const champ = await screen.findByRole('searchbox', { name: 'Chercher dans mes tâches' })
      await waitFor(() => expect(champ).toHaveFocus())
      contenu.focus()
      expect(champ).toHaveFocus()
    } finally { contenu.remove() }
  })

  it('R2-129 — une croix à nous efface la recherche et rend le curseur au champ ; absente quand le champ est vide', async () => {
    const user = userEvent.setup()
    monter('/taches/recherche')
    const champ = await screen.findByRole('searchbox', { name: 'Chercher dans mes tâches' })
    expect(screen.queryByRole('button', { name: 'Effacer la recherche' })).toBeNull()
    await user.type(champ, 'devis')
    await user.click(screen.getByRole('button', { name: 'Effacer la recherche' }))
    expect(champ).toHaveValue('')
    expect(champ).toHaveFocus()
    expect(screen.queryByRole('button', { name: 'Effacer la recherche' })).toBeNull()
  })

  it('R2-129 — une faute de frappe trouve quand même : « fourniseur » rend « Appeler le fournisseur », dit pourquoi', async () => {
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [] } })
    api.listerToutesLesTaches.mockResolvedValue([
      item(60, 'Appeler le fournisseur'), item(61, 'Déclaration TVA'), item(62, 'Commander les panneaux', { statut: 'fait' }),
    ])
    monter('/taches/recherche?q=fourniseur')
    const ouvertes = await screen.findByRole('region', { name: 'Ouvertes (1)' })
    expect(within(ouvertes).getByText('Appeler le fournisseur')).toBeInTheDocument()
    expect(screen.getByText('Rien de tel pour « fourniseur » : voici ce qui s\'en approche.')).toBeInTheDocument()
    expect(screen.queryByText('Rien pour « fourniseur »')).toBeNull()
  })

  it('R2-129 — la tolérance ignore les accents et ne devine pas au hasard : deux fautes ou un mot trop court ne trouvent rien', async () => {
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [] } })
    api.listerToutesLesTaches.mockResolvedValue([item(70, 'Déclaration TVA'), item(71, 'Appeler le fournisseur')])
    monter('/taches/recherche?q=declaraton')
    expect(await screen.findByRole('region', { name: 'Ouvertes (1)' })).toHaveTextContent('Déclaration TVA')
    cleanup()
    monter('/taches/recherche?q=fornisseurs')
    expect(await screen.findByText('Rien pour « fornisseurs »')).toBeInTheDocument()
    cleanup()
    monter('/taches/recherche?q=tba')
    expect(await screen.findByText('Rien pour « tba »')).toBeInTheDocument()
  })

  it('R2-129 — rien de trouvé : un pictogramme au-dessus de la phrase ; les filtres n\'ont plus de ▾ en texte', async () => {
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [] } })
    const { container } = monter('/taches/recherche?q=zzz')
    expect(await screen.findByText('Rien pour « zzz »')).toBeInTheDocument()
    expect(container.querySelector('.vide-etat .vide-picto svg')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Projet' }).textContent).not.toContain('▾')
    expect(screen.getByRole('button', { name: 'Projet' }).querySelector('svg')).not.toBeNull()
  })

  it('R3-093 — ↓ depuis le champ va au premier résultat ; sans résultat il ne bouge pas', async () => {
    const user = userEvent.setup()
    monter()
    const ouvertes = await screen.findByRole('region', { name: 'Ouvertes (2)' })
    const champ = screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' })
    expect(champ).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(ouvertes.querySelector('[data-ligne] .ligne-corps-bouton')).toHaveFocus()
    await user.keyboard('j')
    expect(ouvertes.querySelectorAll('[data-ligne] .ligne-corps-bouton')[1]).toHaveFocus()
    cleanup()
    api.rechercher.mockResolvedValue({ data: { projets: [], taches: [] } })
    monter('/taches/recherche?q=zzqxw')
    await screen.findByText('Rien pour « zzqxw »')
    const vide = screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' })
    vide.focus()
    await user.keyboard('{ArrowDown}')
    expect(vide).toHaveFocus()
  })

  it('R3-093 — « Ajoutées récemment » : les ouvertes, la dernière notée en haut, dix au plus, lues en entier', async () => {
    const user = userEvent.setup()
    const notees = Array.from({ length: 12 }, (_, i) => item(100 + i, `Tâche notée ${i + 1}`, { jour_prevu: null }))
    api.listerToutesLesTaches.mockResolvedValue([...notees, item(200, 'Faite hier', { statut: 'fait' })])
    monter('/taches/recherche')
    await user.click(await screen.findByRole('checkbox', { name: 'Ajoutées récemment' }))
    const ouvertes = await screen.findByRole('region', { name: 'Ouvertes (10)' })
    const titres = [...ouvertes.querySelectorAll('[data-ligne] .titre')].map((t) => t.textContent)
    expect(titres[0]).toBe('Tâche notée 12')
    expect(titres[9]).toBe('Tâche notée 3')
    expect(screen.queryByText('Faite hier')).toBeNull()
    expect(api.listerToutesLesTaches).toHaveBeenCalled()
    expect(api.listerTaches).not.toHaveBeenCalled()
  })

  it('R2-036 — j et k parcourent les résultats ; dans le champ ce sont des lettres', async () => {
    const user = userEvent.setup()
    monter()
    const ouvertes = await screen.findByRole('region', { name: 'Ouvertes (2)' })
    const titres = () => [...ouvertes.querySelectorAll('[data-ligne] .ligne-corps-bouton')]
    await user.type(screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' }), 'jk')
    expect(screen.getByRole('searchbox', { name: 'Chercher dans mes tâches' })).toHaveValue('devisjk')
    await user.click(document.body)
    await user.keyboard('j')
    expect(titres()[0]).toHaveFocus()
    await user.keyboard('j')
    expect(titres()[1]).toHaveFocus()
    await user.keyboard('k')
    expect(titres()[0]).toHaveFocus()
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

  it('Raccord F2 — « Aujourd\'hui » et « 7 prochains jours » passent par `periode` du serveur, le tri servi suit', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('button', { name: 'Plus de filtres' }))
    await user.click(screen.getByRole('checkbox', { name: '7 prochains jours' }))
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

  it('F4 revue #7 — « Annuler » relit CETTE tâche seule : la ligne rouverte garde la version rendue par le serveur', async () => {
    const user = userEvent.setup()
    api.terminerTache.mockResolvedValue({ data: { tache: { ...MIXTE.taches[0], statut: 'fait' }, geste_id: 9 } })
    api.lireTache.mockResolvedValue({ data: { ...MIXTE.taches[0], lock_version: 11 } })
    monter()
    await screen.findByRole('region', { name: 'Ouvertes (2)' })
    await user.click(screen.getByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(9))
    await waitFor(() => expect(api.lireTache).toHaveBeenCalledWith(20))
    expect(await screen.findByRole('region', { name: 'Ouvertes (2)' })).toBeInTheDocument()
    expect(api.rechercher).toHaveBeenCalledTimes(1) // la recherche n'est pas relancée
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

  it('passe visuelle n° 63 — lignes de tâche (supprimees.html) : Restaurer, « Sans projet » ou le projet, jour de suppression', async () => {
    api.listerSupprimees.mockResolvedValue({ data: { ...supprimees, taches: [
      ...supprimees.taches,
      { ...supprimees.taches[0], item: { ...supprimees.taches[0].item, id: 43, titre: 'Rails', projet: { id: 3, nom: 'Ventes', couleur: 'vert', priorite: 3 } } },
    ] } })
    render(<MemoryRouter><Supprimees aujourdhui={AUJOURD} /></MemoryRouter>)
    await screen.findByText('Timbres')
    expect(screen.getByText('Supprimées depuis moins de 30 jours.')).toHaveClass('es-sous')
    const lignes = [...document.querySelectorAll('section[aria-label="Supprimées récemment"] [role="listitem"]')]
    expect(lignes.every((l) => l.matches('.ligne.es-supprimee') && l.firstElementChild.matches('.case'))).toBe(true)
    const metas = lignes.map((l) => [...l.querySelector('.meta').children].map((e) => e.textContent))
    // supprimees.json : le projet le 15/11 à 10:00, « Timbres » (sans projet) le 16/11 à 11:00 — jour servi, heure du Maroc
    expect(metas).toEqual([['Restaurer', 'dim. 15/11'], ['Restaurer', 'Sans projet', 'lun. 16/11'], ['Restaurer', 'Ventes', 'lun. 16/11']])
    expect(lignes[1].querySelector('.meta > button')).toHaveClass('es-action')
    // Derniers gestes : l'heure du geste (le jour même) ou son jour, le message, puis « Annuler » en lien
    const geste = within(screen.getByRole('region', { name: 'Derniers gestes' })).getAllByRole('listitem')[0]
    expect(geste).toHaveClass('es-geste')
    // R2-125 : la tâche touchée suit le message (`titre`, servi par `gestes/`)
    expect([...geste.children].map((e) => e.textContent)).toEqual(['09:20', 'Reportée à jeu. 19 · Appeler le fournisseur', 'Annuler'])
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
    await user.click(within(section).getByRole('button', { name: 'Annuler : Reportée à jeu. 19 · Appeler le fournisseur' }))
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
